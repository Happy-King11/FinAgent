"""应用依赖容器：集中组装可替换的领域服务和基础设施。"""

from app.agents.advisor import Advisor
from app.agents.risk import RiskAgent
from app.agents.router import IntentRouter
from app.observability.audit import AuditLog
from app.observability.sql_audit import SQLAuditLog
from app.pipelines.compliance_sensitive import ComplianceSensitivePipeline
from app.pipelines.consultation import ConsultationPipeline
from app.pipelines.evidence_based import EvidenceBasedPipeline
from app.pipelines.product_explanation import ProductExplanationPipeline
from app.pipelines.valuation import ValuationPipeline
from app.pipelines.registry import PipelineManifest, PipelineRegistry
from app.repositories.memory import ConsultationRepository, DocumentRepository, ProductRepository
from app.retrieval.retriever import Citation, InMemoryRetriever
from app.tools.compliance import ComplianceEngine
from app.core.idempotency import IdempotencyStore, RedisIdempotencyStore
from app.data.providers import FixtureDataProvider
from app.data.quality import DataQualityGate
from app.portfolio.diagnosis import PortfolioDiagnosis
from app.repositories.portfolio import PersistentPortfolioDiagnosisRepository
from app.tools.gateway import ToolGateway
from app.tools.financial import register_finance_tools
from app.tools.registry import ToolManifest
from app.core.config import get_settings
from app.infrastructure.cache.client import create_redis_client
from app.infrastructure.database.session import create_session_factory
from app.repositories.sql import SQLConsultationRepository, SQLDocumentRepository, SQLProductRepository
from app.repositories.workflow import MemoryWorkflowRecordStore, SQLWorkflowRecordStore
from app.application.document_indexing import DocumentIndexer
from app.infrastructure.vector_store.factory import create_vector_store
from app.llm.embeddings import HashingEmbedding, OpenAICompatibleEmbedding
from app.llm.openai_compatible import OpenAICompatibleClient
from app.infrastructure.object_storage.factory import create_object_storage
from app.runtime import EventBus, HookRunner, RecoveryPolicy
from app.runtime.checkpoints import CheckpointStore


class Container:
    def __init__(self) -> None:
        # PoC 默认使用内存实现；切换生产设施时只替换此处组装关系。
        settings = get_settings()
        if settings.app_env == "production":
            # 当前仓储仍是 PoC 内存实现；生产必须先替换为 SQLAlchemy/Redis 仓储，禁止静默丢数据。
            raise RuntimeError("production startup blocked: persistent repository wiring is required")
        if settings.persistence_backend == "postgresql":
            session_factory = create_session_factory()
            self.products = SQLProductRepository(session_factory)
            self.documents = SQLDocumentRepository(session_factory)
            self.consultations = SQLConsultationRepository(session_factory)
        else:
            self.products = ProductRepository()
            self.documents = DocumentRepository()
            self.consultations = ConsultationRepository()
        self.retriever = InMemoryRetriever()
        self.vector_store = create_vector_store()
        if settings.embedding_provider == "openai_compatible":
            self.embedding_provider = OpenAICompatibleEmbedding(
                settings.embedding_base_url,
                settings.embedding_api_key,
                settings.embedding_model,
                settings.embedding_dimension,
                settings.embedding_timeout_seconds,
            )
        else:
            self.embedding_provider = HashingEmbedding(settings.embedding_dimension)
        self.document_indexer = DocumentIndexer(self.embedding_provider, self.vector_store)
        # The vector index is rebuildable; PostgreSQL remains the document authority.
        for document in self.documents.list(settings.default_tenant_id):
            if document.status == "ready":
                self.retriever.add(document)
                try:
                    self.document_indexer.index(document)
                except (RuntimeError, ValueError):
                    # A local provider may be unavailable; the rebuildable keyword index remains usable.
                    continue
        if settings.persistence_backend == "postgresql":
            self.audit = SQLAuditLog(session_factory, settings.audit_genesis_prefix)
        else:
            self.audit = AuditLog()
        self.compliance = ComplianceEngine()
        self.router = IntentRouter()
        self.risk_agent = RiskAgent()
        self.advisor = Advisor(
            OpenAICompatibleClient(
                settings.llm_base_url,
                settings.llm_api_key,
                settings.llm_model,
                max_tokens=settings.llm_max_tokens,
            )
            if settings.llm_provider == "openai_compatible" and settings.llm_base_url
            else None,
            timeout_seconds=settings.llm_timeout_seconds,
        )
        self.product_pipeline = ProductExplanationPipeline()
        self.consultation_pipeline = ConsultationPipeline()
        self.valuation_pipeline = ValuationPipeline()
        self.pipeline_registry = PipelineRegistry()
        self.pipeline_registry.register(
            PipelineManifest(
                "product_explanation",
                "1.0.0",
                ("product_explanation",),
                ("question",),
                allowed_tools=("product_lookup",),
                output_schema="ProductExplanationResult",
            ),
            self.product_pipeline,
        )
        self.pipeline_registry.register(
            PipelineManifest(
                "financial_knowledge",
                "1.0.0",
                ("financial_knowledge",),
                ("question",),
                allowed_tools=("knowledge_search",),
                output_schema="FinancialKnowledgeResult",
            ),
            self.consultation_pipeline,
        )
        self.pipeline_registry.register(
            PipelineManifest(
                "valuation_analysis",
                "1.0.0",
                ("valuation_analysis",),
                ("question",),
                allowed_tools=("dcf_calculate", "wacc_calculate", "comparable_valuation", "scenario_calculate"),
                risk_level="medium",
                output_schema="ValuationAnalysisResult",
            ),
            self.valuation_pipeline,
        )
        evidence_scenes = {
            "single_stock_research": EvidenceBasedPipeline(
                "single_stock_research",
                "单股研究不输出直接买卖指令、模型目标价或仓位建议。",
                ("structured_security_data",),
            ),
            "portfolio_diagnosis": EvidenceBasedPipeline(
                "portfolio_diagnosis",
                "自然语言咨询未携带组合引用和已确认风险画像，因此未执行组合计算。",
                ("portfolio_ref", "confirmed_risk_profile"),
            ),
            "financial_statement_analysis": EvidenceBasedPipeline(
                "financial_statement_analysis",
                "当前仅整理授权财报事实；缺少结构化报表时不计算财务指标。",
                ("structured_financial_statements",),
            ),
            "risk_assessment": EvidenceBasedPipeline(
                "risk_assessment",
                "风险等级和处置动作由确定性 Risk Policy 生成，Risk Agent 不能覆盖。",
                ("risk_subject",),
            ),
            "compliance_consultation": EvidenceBasedPipeline(
                "compliance_consultation",
                "合规咨询仅解释版本化规则和授权制度，不构成法律意见。",
            ),
        }
        for scene_id, pipeline in evidence_scenes.items():
            self.pipeline_registry.register(
                PipelineManifest(
                    scene_id,
                    "1.0.0",
                    (scene_id,),
                    ("question",),
                    allowed_tools=(
                        ("knowledge_search", "dcf_calculate", "wacc_calculate", "comparable_valuation", "scenario_calculate")
                        if scene_id == "valuation_analysis"
                        else ("knowledge_search",)
                    ),
                    risk_level="medium" if scene_id != "compliance_consultation" else "high",
                    output_schema=f"{''.join(part.title() for part in scene_id.split('_'))}Result",
                ),
                pipeline,
            )
        # Retained as a deterministic rule adapter for direct compliance checks;
        # it is not an additional user-facing scene.
        self.compliance_pipeline = ComplianceSensitivePipeline(self.compliance)
        self.tool_gateway = ToolGateway(self.compliance)
        register_finance_tools(self.tool_gateway)
        self.idempotency = RedisIdempotencyStore(create_redis_client()) if settings.redis_idempotency_enabled else IdempotencyStore()
        self.data_provider = FixtureDataProvider()
        self.quality_gate = DataQualityGate()
        if settings.persistence_backend == "postgresql":
            self.workflow_records = SQLWorkflowRecordStore(session_factory)
        else:
            self.workflow_records = MemoryWorkflowRecordStore()
        self.checkpoints = CheckpointStore(self.workflow_records)
        self.events = EventBus()
        self.hooks = HookRunner()
        self.recovery_policy = RecoveryPolicy()
        self.portfolio_diagnosis = PortfolioDiagnosis()
        self.portfolio_diagnoses = PersistentPortfolioDiagnosisRepository(self.workflow_records)
        self.object_storage = None
        if settings.object_storage_enabled:
            self.object_storage = create_object_storage()

        def search_documents(tenant_id: str, query: str, limit: int = 5):
            # PostgreSQL is authoritative; indexing is performed on startup and document writes.
            # Queries must never delete or rebuild the shared index.
            try:
                query_embedding = self.embedding_provider.embed(query)
            except (RuntimeError, ValueError):
                query_embedding = None
            if query_embedding:
                try:
                    vector_results = self.vector_store.search(
                        tenant_id=tenant_id,
                        query=query,
                        limit=limit,
                        embedding=query_embedding,
                    )
                except (RuntimeError, ValueError):
                    vector_results = []
                filtered_results = [
                    item
                    for item in vector_results
                    if item.get("tenant_id") == tenant_id
                    and self._document_belongs_to_tenant(item.get("document_id", ""), tenant_id)
                ]
                if filtered_results:
                    return [
                        (
                            item["text"],
                            Citation(
                                item["document_id"],
                                item["metadata"].get("object_version", "1"),
                                item["metadata"].get("title", ""),
                                item["metadata"].get("source", ""),
                                sha256=item["metadata"].get("sha256"),
                            ),
                        )
                        for item in filtered_results
                        # Defense in depth: the authoritative repository remains the tenant boundary.
                        if item.get("tenant_id") == tenant_id
                        and self._document_belongs_to_tenant(item.get("document_id", ""), tenant_id)
                    ]
            # Keyword retrieval remains an explicit availability fallback.
            return [
                (text, citation)
                for text, citation in self.retriever.search(tenant_id, query, limit)
                if self._document_belongs_to_tenant(citation.document_id, tenant_id)
            ]

        self.search_documents = search_documents

        self.tool_gateway.register(
            "product_lookup",
            lambda tenant_id, query: self.products.find_by_name(tenant_id, query),
            ToolManifest(
                tool_id="product_lookup",
                input_schema={
                    "type": "object",
                    "required": ["tenant_id", "query"],
                    "properties": {"tenant_id": {"type": "string"}, "query": {"type": "string"}},
                },
                output_schema={"type": "array"},
                cache_ttl_seconds=30,
            ),
        )

        self.tool_gateway.register(
            "knowledge_search",
            search_documents,
            ToolManifest(
                tool_id="knowledge_search",
                input_schema={
                    "type": "object",
                    "required": ["tenant_id", "query"],
                    "properties": {"tenant_id": {"type": "string"}, "query": {"type": "string"}},
                },
                output_schema={"type": "array"},
                cache_ttl_seconds=30,
            ),
        )

    def _document_belongs_to_tenant(self, document_id: str, tenant_id: str) -> bool:
        """Verify the authoritative document tenant before exposing a hit."""
        if not document_id or not tenant_id:
            return False
        try:
            self.documents.get(document_id, tenant_id)
        except Exception:
            return False
        return True
