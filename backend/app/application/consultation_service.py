"""咨询用例服务：驱动路由、合规、检索、回答和审计。"""

from uuid import uuid4

from app.application.container import Container
from app.core.constants import ConsultationStatus, RiskLevel
from app.core.exceptions import DomainError, NotFoundError
from app.domain.entities import ConsultationCase, utcnow
from app.tools.gateway import ToolExecutionContext
from app.runtime import FailureInfo, RuntimeContext, RuntimeEvent
from app.pipelines.types import PipelineOutput
from app.risk import RiskPolicyInput, RiskSubjectType


class ConsultationService:
    def __init__(self, container: Container) -> None:
        self.container = container

    def get(self, case_id: str, tenant_id: str) -> ConsultationCase:
        """Return a consultation only when it belongs to the requested tenant."""
        return self.container.consultations.get(case_id, tenant_id)

    def create(
        self,
        *,
        tenant_id: str,
        user_id: str,
        question: str,
        requested_intent: str | None = None,
        scene_input: dict | None = None,
    ) -> ConsultationCase:
        if not question.strip():
            raise DomainError("INVALID_ARGUMENT", "question must not be empty", 422)
        case = ConsultationCase(
            f"case_{uuid4().hex}",
            tenant_id,
            user_id,
            question,
            scene_input=scene_input,
            requested_intent=requested_intent,
        )
        self.container.consultations.add(case, case.id)
        self.container.audit.append(case_id=case.id, tenant_id=tenant_id, event_type="consultation.created", actor=user_id, payload={"question": question})
        self.execute(case)
        return case

    def reset_for_message(self, case: ConsultationCase, question: str, actor: str) -> ConsultationCase:
        """Accept a new message through the state boundary before re-execution."""
        if not question.strip():
            raise DomainError("INVALID_ARGUMENT", "question must not be empty", 422)
        if case.status in {ConsultationStatus.CANCELLED, ConsultationStatus.BLOCKED, ConsultationStatus.EXPIRED}:
            raise DomainError("INVALID_STATE", "case cannot accept messages", 409)
        case.question = question
        case.answer = None
        case.warnings = []
        case.citations = []
        case.compliance = None
        case.result = {}
        case.risk_assessment = None
        case.confirmation_required = False
        case.confirmed_at = None
        case.status = ConsultationStatus.RECEIVED
        case.version += 1
        case.updated_at = utcnow()
        self.container.consultations.add(case, case.id)
        self.container.audit.append(
            case_id=case.id,
            tenant_id=case.tenant_id,
            event_type="consultation.message_added",
            actor=actor,
            payload={"version": case.version},
        )
        return case

    def confirm(self, case: ConsultationCase, *, confirmed: bool, actor: str) -> None:
        """Apply exactly one confirmation transition, then resume execution."""
        if case.status != ConsultationStatus.WAITING_CONFIRMATION:
            raise DomainError("INVALID_STATE", "case is not waiting for confirmation", 409)
        if not confirmed:
            self.transition(case, ConsultationStatus.CANCELLED, actor, reason="user_declined")
            return
        case.confirmed_at = utcnow()
        case.confirmation_required = True
        self.transition(case, ConsultationStatus.EXECUTING, actor, confirmed=True)
        self.execute(case)

    def transition(self, case: ConsultationCase, target: ConsultationStatus, actor: str, **payload) -> ConsultationCase:
        """执行唯一状态迁移入口，并记录版本和审计。"""
        allowed = {
            ConsultationStatus.RECEIVED: {ConsultationStatus.CLASSIFIED, ConsultationStatus.CANCELLED},
            ConsultationStatus.CLASSIFIED: {ConsultationStatus.CLARIFICATION_REQUIRED, ConsultationStatus.COMPLIANCE_PRECHECK, ConsultationStatus.BLOCKED, ConsultationStatus.FAILED},
            ConsultationStatus.CLARIFICATION_REQUIRED: {ConsultationStatus.RECEIVED, ConsultationStatus.CANCELLED, ConsultationStatus.EXPIRED},
            ConsultationStatus.COMPLIANCE_PRECHECK: {ConsultationStatus.EXECUTING, ConsultationStatus.WAITING_CONFIRMATION, ConsultationStatus.HUMAN_REVIEW, ConsultationStatus.BLOCKED, ConsultationStatus.FAILED},
            ConsultationStatus.EXECUTING: {ConsultationStatus.COMPLIANCE_POSTCHECK, ConsultationStatus.WAITING_CONFIRMATION, ConsultationStatus.HUMAN_REVIEW, ConsultationStatus.PARTIAL_SUCCESS, ConsultationStatus.BLOCKED, ConsultationStatus.FAILED, ConsultationStatus.CANCELLED},
            ConsultationStatus.WAITING_CONFIRMATION: {ConsultationStatus.EXECUTING, ConsultationStatus.CANCELLED, ConsultationStatus.EXPIRED},
            ConsultationStatus.HUMAN_REVIEW: {ConsultationStatus.COMPLIANCE_POSTCHECK, ConsultationStatus.CANCELLED, ConsultationStatus.EXPIRED},
            ConsultationStatus.COMPLIANCE_POSTCHECK: {ConsultationStatus.COMPLETED, ConsultationStatus.PARTIAL_SUCCESS, ConsultationStatus.BLOCKED, ConsultationStatus.HUMAN_REVIEW, ConsultationStatus.FAILED},
        }
        if target not in allowed.get(case.status, set()):
            raise DomainError("INVALID_STATE", f"cannot transition {case.status.value} -> {target.value}", 409)
        previous = case.status
        case.status = target
        case.version += 1
        case.updated_at = utcnow()
        self.container.audit.append(case_id=case.id, tenant_id=case.tenant_id, event_type="consultation.status_changed", actor=actor, payload={"from": previous.value, "to": target.value, "version": case.version, **payload})
        self.container.consultations.add(case, case.id)
        self.container.events.publish(RuntimeEvent.from_context(RuntimeContext.from_case(case), "consultation.status_changed", payload={"from": previous.value, "to": target.value, "version": case.version}))
        self.container.hooks.on_state_transition(RuntimeContext.from_case(case), {"from": previous.value, "to": target.value, "version": case.version})
        return case

    def execute(self, case: ConsultationCase) -> None:
        """Run one consultation with isolated runtime observation and failure handling."""
        context = RuntimeContext.from_case(case)
        self.container.hooks.before_run(context)
        self._publish(context, "consultation.started")
        try:
            self._execute(case)
            final_context = RuntimeContext.from_case(case).with_status(case.status.value)
            self.container.hooks.after_run(final_context, {"status": case.status.value})
            self._publish(final_context, "consultation.completed", payload={"status": case.status.value})
        except DomainError as exc:
            failure = FailureInfo.from_exception(exc, trace_id=case.trace_id, source="consultation")
            self.container.hooks.on_error(context, failure)
            self._publish(context, "consultation.failed", payload={"error_code": exc.code})
            raise
        except Exception as exc:
            failure = FailureInfo.from_exception(exc, trace_id=case.trace_id, source="consultation")
            self.container.hooks.on_error(context, failure)
            try:
                if case.status in {
                    ConsultationStatus.CLASSIFIED,
                    ConsultationStatus.COMPLIANCE_PRECHECK,
                    ConsultationStatus.EXECUTING,
                    ConsultationStatus.COMPLIANCE_POSTCHECK,
                }:
                    self.transition(case, ConsultationStatus.FAILED, "application", reason="runtime_failure")
                case.warnings.append("当前咨询流程不可用，请稍后重试。")
                self.container.consultations.add(case, case.id)
            except Exception:
                pass
            self._publish(RuntimeContext.from_case(case), "consultation.failed", payload={"error_code": failure.error_code})
            raise DomainError("RUNTIME_EXECUTION_FAILED", "当前咨询流程不可用，请稍后重试。", 503) from exc
        finally:
            self.container.hooks.finally_run(RuntimeContext.from_case(case))

    def _publish(self, context: RuntimeContext, event_type: str, *, payload: dict | None = None) -> None:
        self.container.events.publish(RuntimeEvent.from_context(context, event_type, payload=payload or {}))

    def _execute(self, case: ConsultationCase) -> None:
        # 状态变化严格按“分类 -> 预审 -> 执行 -> 后审”顺序推进。
        route = self.container.router.route(case.question, case.trace_id, case.requested_intent)
        self._publish(RuntimeContext.from_case(case), "consultation.classified", payload={"intent": route.primary_intent, "risk_level": route.risk_level.value})
        self.container.hooks.after_route(RuntimeContext.from_case(case), {"intent": route.primary_intent, "risk_level": route.risk_level.value})
        case.intent = route.primary_intent
        case.risk_level = route.risk_level
        if case.status == ConsultationStatus.RECEIVED:
            self.transition(case, ConsultationStatus.CLASSIFIED, "router")
            self.transition(case, ConsultationStatus.COMPLIANCE_PRECHECK, "application")
            self.container.audit.append(case_id=case.id, tenant_id=case.tenant_id, event_type="router.completed", actor="router", payload=route.as_dict())
            pre = self.container.compliance.check(case.question, phase="pre")
            case.compliance = pre.as_dict()
            self.container.audit.append(case_id=case.id, tenant_id=case.tenant_id, event_type="compliance.precheck", actor="compliance", payload=pre.as_dict())
            self._publish(RuntimeContext.from_case(case), "consultation.compliance_checked", payload={"phase": "pre", "decision": pre.decision})
            if pre.decision == "block":
                self.transition(case, ConsultationStatus.BLOCKED, "compliance")
                case.warnings.append(pre.reason or "请求被合规规则阻断")
                self._apply_risk_assessment(case, compliance_decision=pre.decision)
                self.container.consultations.add(case, case.id)
                return
            if pre.decision == "require_approval":
                self.transition(case, ConsultationStatus.HUMAN_REVIEW, "compliance")
                case.warnings.append(pre.reason or "该问题需要人工合规复核。")
                self._apply_risk_assessment(case, compliance_decision=pre.decision)
                self.container.audit.append(case_id=case.id, tenant_id=case.tenant_id, event_type="consultation.human_review", actor="compliance", payload=pre.as_dict())
                self.container.consultations.add(case, case.id)
                return
            if route.requires_clarification:
                self.transition(case, ConsultationStatus.CLARIFICATION_REQUIRED, "router")
                case.warnings.append("问题意图置信度不足，请补充产品名称、资料或目标。")
                self._apply_risk_assessment(case, missing_fields=("clarified_intent",))
                self.container.consultations.add(case, case.id)
                return
            if route.risk_level == RiskLevel.HIGH and case.confirmed_at is None:
                self.transition(case, ConsultationStatus.WAITING_CONFIRMATION, "guardrail")
                case.confirmation_required = True
                case.warnings.append("该咨询属于高风险场景，继续执行前需要用户确认。")
                self.container.consultations.add(case, case.id)
                return
        else:
            pre = self.container.compliance.check(case.question, phase="pre")
        if case.status == ConsultationStatus.COMPLIANCE_PRECHECK:
            self.transition(case, ConsultationStatus.EXECUTING, "pipeline")
        citations: list[dict] = []
        warnings: list[str] = []
        pipeline_output = PipelineOutput("")
        evidence_count = 0
        try:
            manifest, pipeline = self.container.pipeline_registry.resolve(
                route.candidate_pipelines,
                intent=route.primary_intent,
                available_inputs={"question", "scene_input"} if case.scene_input else {"question"},
            )
        except ValueError as exc:
            self.transition(case, ConsultationStatus.FAILED, "pipeline", reason="pipeline_unavailable")
            case.warnings.append("当前咨询流程不可用，请稍后重试。")
            raise DomainError("PIPELINE_UNAVAILABLE", "no eligible pipeline is available", 503) from exc
        tool_context = ToolExecutionContext(
            tenant_id=case.tenant_id,
            user_id=case.user_id,
            confirmed=case.confirmed_at is not None,
            allowed_tools=frozenset(manifest.allowed_tools),
            blocked_tools=frozenset(manifest.blocked_tools),
            case_id=case.id,
            trace_id=case.trace_id,
            pipeline_id=manifest.pipeline_id,
            pipeline_version=manifest.version,
        )
        if route.primary_intent == "product_explanation":
            # 产品解释只读取租户授权产品事实，不调用外部行情。
            products = self.container.tool_gateway.execute("product_lookup", input_text=case.question, context=tool_context, tenant_id=case.tenant_id, query=case.question)
            if not products:
                products = self.container.products.list(case.tenant_id)[:1]
            if products:
                pipeline_output = pipeline.run(products[0], case.question)
                answer = pipeline_output.facts
                evidence_count = 1
            else:
                answer = "没有找到该租户下的授权产品资料。"
                pipeline_output = PipelineOutput(
                    answer,
                    warnings=("缺少授权产品记录，不能解释产品事实。",),
                    missing_fields=("authorized_product",),
                    result={"scene_id": "product_explanation"},
                )
        elif route.primary_intent == "valuation_analysis":
            pipeline_output = pipeline.run(case.scene_input, self.container.tool_gateway, tool_context)
            citations = list(pipeline_output.citations)
            evidence_count = len(citations)
            answer = pipeline_output.facts
        else:
            retrieved = self.container.tool_gateway.execute("knowledge_search", input_text=case.question, context=tool_context, tenant_id=case.tenant_id, query=case.question)
            pipeline_output = pipeline.run(case.question, retrieved)
            citations = list(pipeline_output.citations)
            evidence_count = len(citations)
            self.container.hooks.before_step(RuntimeContext.from_case(case), "advisor")
            answer = self.container.advisor.compose(case.question, pipeline_output.facts, citations, rewrite=pre.rewritten_text)
            self.container.hooks.after_step(RuntimeContext.from_case(case), "advisor", {"citation_count": len(citations)})
        warnings.extend(pipeline_output.warnings)
        case.result = pipeline_output.result
        self.transition(case, ConsultationStatus.COMPLIANCE_POSTCHECK, "compliance")
        post = self.container.compliance.check(answer, phase="post")
        if post.decision == "block":
            self.transition(case, ConsultationStatus.BLOCKED, "compliance")
            case.compliance = post.as_dict()
            case.warnings.append(post.reason or "输出被合规规则阻断")
            self._apply_risk_assessment(
                case,
                compliance_decision=post.decision,
                missing_fields=pipeline_output.missing_fields,
                evidence_required=route.requires_retrieval,
                evidence_count=evidence_count,
            )
            self.container.consultations.add(case, case.id)
            return
        case.answer = answer
        case.citations = citations
        case.warnings.extend(warnings)
        case.compliance = post.as_dict() if post.decision != "allow" else pre.as_dict()
        self._apply_risk_assessment(
            case,
            compliance_decision=post.decision,
            missing_fields=pipeline_output.missing_fields,
            evidence_required=route.requires_retrieval,
            evidence_count=evidence_count,
        )
        self.transition(case, ConsultationStatus.COMPLETED, "application")
        self.container.audit.append(
            case_id=case.id,
            tenant_id=case.tenant_id,
            event_type="consultation.completed",
            actor="application",
            payload={"status": case.status.value, "citations": citations, "risk_assessment": case.risk_assessment},
        )

    def _apply_risk_assessment(
        self,
        case: ConsultationCase,
        *,
        compliance_decision: str = "allow",
        missing_fields: tuple[str, ...] = (),
        evidence_required: bool = False,
        evidence_count: int = 0,
    ) -> None:
        assessment = self.container.risk_agent.assess(
            RiskPolicyInput(
                subject_type=self._risk_subject(case.intent, case.question),
                compliance_decision=compliance_decision,
                missing_fields=missing_fields,
                warnings=tuple(case.warnings),
                evidence_required=evidence_required,
                evidence_count=evidence_count,
            )
        )
        case.risk_assessment = assessment.as_dict()
        case.risk_level = assessment.decision.risk_level

    @staticmethod
    def _risk_subject(intent: str | None, question: str) -> RiskSubjectType:
        if intent == "product_explanation":
            return RiskSubjectType.PRODUCT
        if intent in {"single_stock_research", "valuation_analysis", "financial_statement_analysis"}:
            return RiskSubjectType.SECURITY
        if intent == "portfolio_diagnosis":
            return RiskSubjectType.PORTFOLIO
        if intent == "risk_assessment":
            text = question.lower()
            if any(token in text for token in ("用户", "客户", "承受能力", "risk profile")):
                return RiskSubjectType.USER
            if any(token in text for token in ("产品", "基金", "理财")):
                return RiskSubjectType.PRODUCT
            if any(token in text for token in ("股票", "个股", "证券")):
                return RiskSubjectType.SECURITY
            if any(token in text for token in ("组合", "持仓", "portfolio")):
                return RiskSubjectType.PORTFOLIO
        return RiskSubjectType.CONSULTATION

    def _set_status(self, case: ConsultationCase, target: ConsultationStatus, actor: str) -> None:
        """Compatibility wrapper; new code must use transition."""
        self.transition(case, target, actor)
