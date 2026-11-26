"""v1 HTTP 路由：负责参数校验、依赖注入和响应转换。"""

from uuid import uuid4
from hashlib import sha256

from fastapi import APIRouter, Depends, Header, HTTPException

from app.api.deps import get_container, request_context, require_api_permission
from app.api.v1.schemas import ApiError, ApiResponse, ConsultationCreate, ConsultationMessage, ConfirmationRequest, DocumentCreate, KnowledgeSearch, PortfolioDiagnosisCreate, PortfolioReview, ProfileUpdate, SuitabilityRequest, ReportRequest
from app.application.container import Container
from app.application.consultation_service import ConsultationService
from app.domain.entities import Document, Product
from app.core.constants import RiskLevel, ConsultationStatus
from app.core.exceptions import DomainError
from app.application.portfolio_service import PortfolioDiagnosisService
from app.portfolio.diagnosis import RiskProfile

router = APIRouter()


def response(data, *, trace_id: str, warnings=None, citations=None, compliance=None):
    # 所有成功接口统一携带链路标识、警告、引用和合规摘要。
    return ApiResponse(request_id=f"req_{uuid4().hex}", trace_id=trace_id, data=data, warnings=[{"message": x} for x in (warnings or [])], citations=citations or [], compliance=compliance)


def consultation_data(case, *, include_question: bool = False) -> dict:
    data = {
        "case_id": case.id,
        "status": case.status.value,
        "answer": case.answer,
        "intent": case.intent,
        "result": case.result,
        "risk_assessment": case.risk_assessment,
    }
    if include_question:
        data["question"] = case.question
    return data


@router.get("/health/live")
def live():
    return {"status": "ok"}


@router.get("/health/ready")
def ready():
    from app.main import ready as root_ready
    return root_ready()


@router.post("/consultations", response_model=ApiResponse[dict])
def create_consultation(payload: ConsultationCreate, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), context=Depends(request_context), container: Container = Depends(get_container)):
    # 幂等范围包含租户和用户，防止不同主体共享同一请求结果。
    tenant_id, user_id = context
    if not idempotency_key:
        raise HTTPException(400, detail={"code": "INVALID_ARGUMENT", "message": "Idempotency-Key is required"})
    service = ConsultationService(container)
    cached = container.idempotency.get_or_raise(f"consultations:create:{tenant_id}:{user_id}", idempotency_key, payload.model_dump()) if hasattr(container, "idempotency") else None
    if cached:
        return cached
    case = service.create(
        tenant_id=tenant_id,
        user_id=user_id,
        question=payload.question,
        requested_intent=payload.requested_intent,
        scene_input=payload.scene_input.model_dump() if payload.scene_input else None,
    )
    result = response(consultation_data(case), trace_id=case.trace_id, warnings=case.warnings, citations=case.citations, compliance=case.compliance)
    container.idempotency.put(f"consultations:create:{tenant_id}:{user_id}", idempotency_key, payload.model_dump(), result)
    return result


@router.get("/consultations/{case_id}", response_model=ApiResponse[dict])
def get_consultation(case_id: str, context=Depends(request_context), container: Container = Depends(get_container)):
    tenant_id, _ = context
    case = ConsultationService(container).get(case_id, tenant_id)
    return response(consultation_data(case, include_question=True), trace_id=case.trace_id, warnings=case.warnings, citations=case.citations, compliance=case.compliance)


@router.post("/consultations/{case_id}/messages", response_model=ApiResponse[dict])
def append_message(case_id: str, payload: ConsultationMessage, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), context=Depends(request_context), container: Container = Depends(get_container)):
    tenant_id, user_id = context
    if not idempotency_key:
        raise HTTPException(400, detail={"code": "INVALID_ARGUMENT", "message": "Idempotency-Key is required"})
    scope = f"consultations:message:{tenant_id}:{user_id}:{case_id}"
    cached = container.idempotency.get_or_raise(scope, idempotency_key, payload.model_dump())
    if cached:
        return cached
    case = ConsultationService(container).get(case_id, tenant_id)
    if case.status in {ConsultationStatus.CANCELLED, ConsultationStatus.BLOCKED, ConsultationStatus.EXPIRED}:
        raise HTTPException(409, detail={"code": "INVALID_STATE", "message": "case cannot accept messages"})
    service = ConsultationService(container)
    service.reset_for_message(case, payload.question, user_id)
    service.execute(case)
    result = response(consultation_data(case), trace_id=case.trace_id, warnings=case.warnings, citations=case.citations, compliance=case.compliance)
    container.idempotency.put(scope, idempotency_key, payload.model_dump(), result)
    return result


@router.post("/consultations/{case_id}/confirm", response_model=ApiResponse[dict])
def confirm_consultation(case_id: str, payload: ConfirmationRequest, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), context=Depends(request_context), container: Container = Depends(get_container)):
    tenant_id, user_id = context
    if not idempotency_key:
        raise HTTPException(400, detail={"code": "INVALID_ARGUMENT", "message": "Idempotency-Key is required"})
    scope = f"consultations:confirm:{tenant_id}:{user_id}:{case_id}"
    cached = container.idempotency.get_or_raise(scope, idempotency_key, payload.model_dump())
    if cached:
        return cached
    case = ConsultationService(container).get(case_id, tenant_id)
    if case.status != ConsultationStatus.WAITING_CONFIRMATION:
        raise HTTPException(409, detail={"code": "INVALID_STATE", "message": "case is not waiting for confirmation"})
    service = ConsultationService(container)
    try:
        service.confirm(case, confirmed=payload.confirmed, actor=user_id)
    except DomainError as exc:
        raise HTTPException(exc.status_code, detail={"code": exc.code, "message": exc.message}) from exc
    result = response(consultation_data(case), trace_id=case.trace_id, warnings=case.warnings, citations=case.citations, compliance=case.compliance)
    container.idempotency.put(scope, idempotency_key, payload.model_dump(), result)
    return result


@router.post("/consultations/{case_id}/cancel", response_model=ApiResponse[dict])
def cancel_consultation(case_id: str, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), context=Depends(request_context), container: Container = Depends(get_container)):
    tenant_id, user_id = context
    if not idempotency_key:
        raise HTTPException(400, detail={"code": "INVALID_ARGUMENT", "message": "Idempotency-Key is required"})
    scope = f"consultations:cancel:{tenant_id}:{user_id}:{case_id}"
    cached = container.idempotency.get_or_raise(scope, idempotency_key, {"cancel": True})
    if cached:
        return cached
    case = ConsultationService(container).get(case_id, tenant_id)
    service = ConsultationService(container)
    service.transition(case, ConsultationStatus.CANCELLED, user_id, reason="user_cancelled")
    result = response({"case_id": case.id, "status": case.status.value}, trace_id=case.trace_id)
    container.idempotency.put(scope, idempotency_key, {"cancel": True}, result)
    return result


@router.get("/audit/{case_id}")
def get_audit(case_id: str, context=Depends(request_context), _: object = Depends(require_api_permission("audit:read")), container: Container = Depends(get_container)):
    tenant_id, _ = context
    events = container.audit.list(case_id, tenant_id)
    if not events:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "audit not found"})
    return {"request_id": f"req_{uuid4().hex}", "trace_id": events[0].payload.get("trace_id", case_id), "data": {"events": [event.__dict__ for event in events], "chain_valid": container.audit.verify(case_id, tenant_id)}}


@router.post("/documents", response_model=ApiResponse[dict])
def create_document(payload: DocumentCreate, context=Depends(request_context), container: Container = Depends(get_container)):
    tenant_id, user_id = context
    document_id = f"doc_{uuid4().hex}"
    # 摘要用于证据定位和文档版本追踪，不覆盖既有文档版本。
    raw_content = payload.content.encode()
    digest = sha256(raw_content).hexdigest()
    object_key = f"tenant/{tenant_id}/documents/{digest}/v1/content.txt"
    if container.object_storage is not None:
        container.object_storage.put(object_key, raw_content, "text/plain; charset=utf-8")
    document = Document(document_id, tenant_id, payload.title, payload.content, digest, payload.source, object_key=object_key)
    container.documents.add(document, document.id)
    container.retriever.add(document)
    try:
        container.document_indexer.index(document)
    except Exception:
        # Indexing is rebuildable; PostgreSQL document persistence remains authoritative.
        pass
    task = None
    if container.workflow_records.__class__.__name__ == "SQLWorkflowRecordStore":
        task_id = f"task_{uuid4().hex}"
        task = {"task_id": task_id, "tenant_id": tenant_id, "task_type": "document_index", "status": "queued", "attempts": 0, "document_id": document.id}
        container.workflow_records.put("task", task_id, tenant_id, task)
        try:
            from app.infrastructure.queue.tasks import rebuild_document_index
            rebuild_document_index.delay(document.id, tenant_id, task_id)
        except Exception:
            task.update(status="failed", error_type="dispatch_failed")
            container.workflow_records.put("task", task_id, tenant_id, task)
    container.audit.append(case_id=document_id, tenant_id=tenant_id, event_type="document.created", actor=user_id, payload={"document_id": document_id, "sha256": digest, "object_key": object_key})
    data = {"document_id": document.id, "status": document.status, "sha256": document.sha256, "object_key": object_key}
    if task:
        data["task"] = task
    return response(data, trace_id=f"trace_{uuid4().hex}")


@router.get("/documents/{document_id}", response_model=ApiResponse[dict])
def get_document(document_id: str, context=Depends(request_context), container: Container = Depends(get_container)):
    tenant_id, _ = context
    document = container.documents.get(document_id, tenant_id)
    return response({"document_id": document.id, "title": document.title, "status": document.status, "object_version": document.object_version, "sha256": document.sha256, "source": document.source, "object_key": document.object_key}, trace_id=f"trace_{uuid4().hex}")


@router.post("/knowledge/search")
def search_knowledge(payload: KnowledgeSearch, context=Depends(request_context), container: Container = Depends(get_container)):
    tenant_id, _ = context
    results = container.search_documents(tenant_id, payload.query, payload.limit)
    return response({"results": [{"snippet": text[:800], "citation": citation.as_dict()} for text, citation in results]}, trace_id=f"trace_{uuid4().hex}", citations=[citation.as_dict() for _, citation in results])


@router.get("/products")
def list_products(context=Depends(request_context), _: object = Depends(require_api_permission("products:read")), container: Container = Depends(get_container)):
    tenant_id, _ = context
    products = container.products.list(tenant_id)
    return response({"items": [product.__dict__ for product in products]}, trace_id=f"trace_{uuid4().hex}")


@router.get("/products/{product_id}")
def get_product(product_id: str, context=Depends(request_context), _: object = Depends(require_api_permission("products:read")), container: Container = Depends(get_container)):
    tenant_id, _ = context
    product = container.products.get(product_id, tenant_id)
    return response(product.__dict__, trace_id=f"trace_{uuid4().hex}")


@router.get("/users/me/profile", response_model=ApiResponse[dict])
def get_profile(context=Depends(request_context), container: Container = Depends(get_container)):
    tenant_id, user_id = context
    profile = container.workflow_records.find("profile", user_id, tenant_id) or {}
    return response(profile, trace_id=f"trace_{uuid4().hex}")


@router.put("/users/me/profile", response_model=ApiResponse[dict])
def update_profile(payload: ProfileUpdate, if_match: str | None = Header(default=None, alias="If-Match"), context=Depends(request_context), container: Container = Depends(get_container)):
    tenant_id, user_id = context
    current = container.workflow_records.find("profile", user_id, tenant_id)
    current_version = int(current.get("version", 0)) if current else 0
    if current and if_match != str(current_version):
        raise HTTPException(409, detail={"code": "STALE_DATA", "message": "profile version is stale"})
    profile = {**payload.model_dump(), "source_type": "user_explicit" if payload.confirmed else "user_explicit"}
    saved = container.workflow_records.put("profile", user_id, tenant_id, profile, expected_version=current_version if current else 0)
    return response(saved, trace_id=f"trace_{uuid4().hex}")


@router.post("/suitability/check", response_model=ApiResponse[dict])
def suitability_check(payload: SuitabilityRequest, context=Depends(request_context), container: Container = Depends(get_container)):
    tenant_id, user_id = context
    profile = container.workflow_records.find("profile", user_id, tenant_id)
    if not profile or not profile.get("confirmed"):
        return response({"status": "insufficient_data", "suitable": False, "missing_fields": ["confirmed_profile"]}, trace_id=f"trace_{uuid4().hex}", warnings=["已确认风险画像缺失"])
    levels = {"low": 1, "medium": 2, "high": 3}
    suitable = levels[profile["risk_level"]] >= levels[payload.product_risk_level]
    return response({"status": "completed", "suitable": suitable, "profile_risk_level": profile["risk_level"], "product_risk_level": payload.product_risk_level}, trace_id=f"trace_{uuid4().hex}")


@router.post("/reports", response_model=ApiResponse[dict])
def create_report(payload: ReportRequest, context=Depends(request_context), container: Container = Depends(get_container)):
    tenant_id, user_id = context
    case = ConsultationService(container).get(payload.case_id, tenant_id)
    report_id = f"report_{uuid4().hex}"
    report = {"report_id": report_id, "tenant_id": tenant_id, "case_id": case.id, "status": "completed", "content": case.answer or "", "citations": case.citations, "version": 1}
    container.workflow_records.put("report", report_id, tenant_id, report)
    container.audit.append(case_id=case.id, tenant_id=tenant_id, event_type="report.created", actor=user_id, payload={"report_id": report_id})
    return response(report, trace_id=case.trace_id, citations=case.citations)


@router.get("/reports/{report_id}", response_model=ApiResponse[dict])
def get_report(report_id: str, context=Depends(request_context), container: Container = Depends(get_container)):
    report = container.workflow_records.find("report", report_id, context[0])
    if not report:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "report not found"})
    return response(report, trace_id=f"trace_{uuid4().hex}", citations=report.get("citations", []))


@router.get("/tasks/{task_id}", response_model=ApiResponse[dict])
def get_task(task_id: str, context=Depends(request_context), container: Container = Depends(get_container)):
    task = container.workflow_records.find("task", task_id, context[0])
    if not task:
        raise HTTPException(404, detail={"code": "TASK_NOT_FOUND", "message": "task not found"})
    return response(task, trace_id=task.get("trace_id", f"trace_{uuid4().hex}"))


@router.post("/portfolio/diagnoses", response_model=ApiResponse[dict])
def create_portfolio_diagnosis(payload: PortfolioDiagnosisCreate, context=Depends(request_context), container: Container = Depends(get_container)):
    tenant_id, user_id = context
    profile = RiskProfile(**payload.risk_profile.model_dump()) if payload.risk_profile else None
    result = PortfolioDiagnosisService(container).create(tenant_id=tenant_id, user_id=user_id, portfolio_id=payload.portfolio_id, risk_profile=profile)
    data = result.as_dict()
    return response(data, trace_id=f"trace_{uuid4().hex}", warnings=result.warnings)


@router.get("/portfolio/diagnoses/{diagnosis_id}", response_model=ApiResponse[dict])
def get_portfolio_diagnosis(diagnosis_id: str, context=Depends(request_context), container: Container = Depends(get_container)):
    tenant_id, _ = context
    result = PortfolioDiagnosisService(container).get(diagnosis_id, tenant_id)
    return response(result.as_dict(), trace_id=f"trace_{uuid4().hex}", warnings=result.warnings)


@router.post("/portfolio/diagnoses/{diagnosis_id}/review", response_model=ApiResponse[dict])
def review_portfolio_diagnosis(diagnosis_id: str, payload: PortfolioReview, context=Depends(request_context), _: object = Depends(require_api_permission("review:write")), container: Container = Depends(get_container)):
    tenant_id, reviewer_id = context
    result = PortfolioDiagnosisService(container).review(diagnosis_id=diagnosis_id, tenant_id=tenant_id, reviewer_id=reviewer_id, decision=payload.decision, note=payload.note)
    return response(result.as_dict(), trace_id=f"trace_{uuid4().hex}", warnings=result.warnings)


def seed_demo(container: Container) -> None:
    # 仅提供本地演示产品，不代表真实金融产品数据。
    product = Product("product-demo-fund", "tenant-demo", "示例稳健债券基金", "公募基金", RiskLevel.LOW, [{"name": "管理费", "value": "0.50%/年"}, {"name": "托管费", "value": "0.10%/年"}], "开放日可赎回", "主要投资于高等级固定收益资产，具体以基金法律文件为准。", ["基金有风险，投资需谨慎。历史表现不代表未来收益。"], "demo-v1")
    container.products.add(product, product.id)
