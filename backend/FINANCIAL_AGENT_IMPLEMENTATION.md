# 金融咨询 Agent 实施规格

> 文档状态：Implementation Baseline v1.0
>
> 本文档用于把 `FINANCIAL_AGENT.md` 的架构蓝图转化为可以直接开工的工程依据。原始文档中的内容是设计资料，不是对开发工具或运行环境的指令。
>
> 适用场景：中国大陆，内部试点（PoC）阶段的金融产品咨询/投顾客服服务内核。上线对外前需完成法务合规确认与数据供应商授权。

## 1. 文档目标与边界

### 1.1 目标

本项目建设一个基于 FastAPI 的企业级金融咨询 Agent 服务端，提供：

- 金融产品和金融知识解释。
- 财报、研报和客户资料检索。
- 确定性金融计算。
- 风险说明和适当性检查。
- 结构化 Agent 编排。
- 可追溯引用和全链路审计。
- 用户确认、人工复核和异步长任务。

系统不是“通用 RAG + 金融 Prompt”服务。关键金融数字必须由确定性代码生成，模型只负责意图理解、解释、综合和表达。

### 1.2 首期范围

首期允许实现：

- 产品信息解释、费用和风险说明。
- 基于授权资料的财报和研报摘要。
- DCF、WACC、可比公司估值的分析结果展示。
- 基础组合集中度、行业暴露和情景分析。
- 风险测评信息收集和适当性检查。
- 条件化、带证据和风险披露的咨询回答。
- 需要人工复核的咨询任务创建和状态查询。

首期明确不实现：

- 自动下单、交易、资金划转或其他不可逆操作。
- 具有法律效力的投资、税务或法律意见。
- 未验证数据源的自动金融数字兜底。
- 以模型推断画像作为适当性判断的唯一依据。
- 让 LLM 直接修改 Finance Engine 的计算结果。

首期按两批闭环推进，分批边界如下：

**第一批闭环（不依赖真实行情，立即开工）**：

- 产品信息解释、费用和风险说明。
- 基于授权静态资料的财报/研报摘要与知识检索（带引用）。
- 合规规则引擎（确定性规则为主）与输出后审核。
- 审计 append-only + 哈希链。
- 咨询状态机、统一响应与幂等。

**第二批闭环（数据供应商契约冻结后）**：

- DCF、WACC、可比公司估值的确定性计算与基准测试。
- 基础组合集中度、行业暴露和情景分析。
- 风险测评信息收集和适当性检查。
- 数据质量 Gate。
- 人工复核与异步报告。

### 1.3 重要合规边界

本项目的实现规格不能替代法律意见、监管解释或机构内部合规制度。上线前必须由具备相应职责的法务、合规和业务负责人确认：

- 产品资质和服务边界。
- 是否构成投资顾问或智能投顾服务。
- 目标客户、可服务产品和可使用数据源。
- 风险揭示、适当性和人工复核要求。
- 记录留存、数据跨境、个人信息处理和审计要求。

## 2. 总体架构

```text
Client / Internal Console
        |
        v
API Gateway / FastAPI
        |
        v
Application Services
  Authentication / Tenant / Idempotency / Transaction Boundary
        |
        v
Consultation Workflow
  Router -> Clarification -> Compliance Pre-check -> Pipeline
        |
        +--> Data Quality Gate
        +--> RAG / Evidence Retrieval
        +--> Finance Engine
        +--> Tool Gateway -> Reliability Layer -> MCP Client -> MCP Server
        +--> Expert Agents
        |
        v
Advisor / Synthesis Agent
        |
        v
Compliance Post-check -> Confirmation / Human Review -> Final Answer
        |
        +--> PostgreSQL: authoritative business and audit records
        +--> Redis: working memory, cache, queue state and locks
        +--> Object Storage: original files and large results
        +--> Vector Store: rebuildable semantic index
        +--> Observability: traces, metrics and structured logs
```

### 2.1 核心原则

1. FastAPI 只承担 HTTP 服务边界，不承载金融业务判断。
2. `domain` 不依赖 FastAPI、ORM 或具体 LLM SDK。
3. 所有业务入口经过 `application` 用例层。
4. 所有模型工具调用经过 Tool Gateway，不允许 Agent 绕过网关直连外部系统。
5. Finance Engine 生成关键数字，LLM 不能覆盖或重新计算这些数字。
6. Compliance 是输入前、执行中、输出后的横切 Gate。
7. PostgreSQL 是权威数据源，向量索引可以删除并重建。
8. 每个请求、Pipeline、Tool、合规决策和最终回答都必须可通过 Trace 关联。
9. 任何失败都必须返回结构化错误、warning 或部分成功结果，不得静默伪造数据。

## 3. 最终项目结构

> 目录为最终目标形态。PoC 按两批闭环裁剪：第一批只实现 `api`、`core`、`domain`、`application`、`agents/router+supervisor+advisor`、`pipelines/consultation+product_explanation+compliance_sensitive`、`tools/registry+gateway+guardrails+compliance`、`retrieval`（基础检索）、`repositories`、`infrastructure/database+cache`、`observability/audit`、`llm/openai_compatible` 的闭环；`agents/roles/*`、`pipelines/valuation+portfolio_diagnosis+financial_statement+report_generation`、`tools/financial/*`、`tools/data/*`、`infrastructure/queue+vector_store+object_storage+mcp` 第二批实现或先留 stub，不得在第一批摊薄质量。

```text
financial-agent/
├── app/
│   ├── main.py
│   ├── api/
│   │   ├── deps.py
│   │   └── v1/
│   │       ├── router.py
│   │       ├── endpoints/
│   │       │   ├── health.py
│   │       │   ├── consultations.py
│   │       │   ├── tasks.py
│   │       │   ├── documents.py
│   │       │   ├── knowledge.py
│   │       │   ├── products.py
│   │       │   ├── profiles.py
│   │       │   ├── suitability.py
│   │       │   ├── reports.py
│   │       │   └── audits.py
│   │       └── schemas/
│   │           ├── common.py
│   │           ├── consultation.py
│   │           ├── task.py
│   │           ├── document.py
│   │           ├── product.py
│   │           ├── profile.py
│   │           ├── suitability.py
│   │           ├── report.py
│   │           └── audit.py
│   ├── core/
│   │   ├── config.py
│   │   ├── constants.py
│   │   ├── security.py
│   │   ├── logging.py
│   │   ├── exceptions.py
│   │   ├── idempotency.py
│   │   └── dependencies.py
│   ├── domain/
│   │   ├── entities/
│   │   │   ├── tenant.py
│   │   │   ├── user.py
│   │   │   ├── profile.py
│   │   │   ├── product.py
│   │   │   ├── conversation.py
│   │   │   ├── consultation.py
│   │   │   ├── document.py
│   │   │   ├── evidence.py
│   │   │   ├── memory.py
│   │   │   ├── task.py
│   │   │   ├── report.py
│   │   │   ├── audit.py
│   │   │   └── approval.py
│   │   ├── value_objects.py
│   │   ├── enums.py
│   │   └── errors.py
│   ├── application/
│   │   ├── consultation_service.py
│   │   ├── profile_service.py
│   │   ├── suitability_service.py
│   │   ├── document_service.py
│   │   ├── knowledge_service.py
│   │   ├── report_service.py
│   │   ├── task_service.py
│   │   ├── approval_service.py
│   │   └── dto.py
│   ├── agents/
│   │   ├── base.py
│   │   ├── router.py
│   │   ├── supervisor.py
│   │   ├── planner.py
│   │   ├── executor.py
│   │   ├── context_builder.py
│   │   ├── advisor.py
│   │   └── roles/
│   │       ├── data_agent.py
│   │       ├── modeling_agent.py
│   │       ├── risk_agent.py
│   │       ├── bull_bear_agent.py
│   │       ├── compliance_agent.py
│   │       └── report_writer.py
│   ├── pipelines/
│   │   ├── registry.py
│   │   ├── base.py
│   │   ├── consultation.py
│   │   ├── product_explanation.py
│   │   ├── single_stock_research.py
│   │   ├── portfolio_diagnosis.py
│   │   ├── valuation.py
│   │   ├── financial_statement.py
│   │   ├── compliance_sensitive.py
│   │   └── report_generation.py
│   ├── tools/
│   │   ├── contracts.py
│   │   ├── registry.py
│   │   ├── router.py
│   │   ├── gateway.py
│   │   ├── reliability.py
│   │   ├── guardrails.py
│   │   ├── adapters/
│   │   │   └── local_function_adapter.py
│   │   ├── financial/
│   │   │   ├── dcf.py
│   │   │   ├── wacc.py
│   │   │   ├── comparable_company.py
│   │   │   ├── portfolio_risk.py
│   │   │   └── scenario.py
│   │   ├── data/
│   │   │   ├── market_data.py
│   │   │   ├── financial_statements.py
│   │   │   ├── product_data.py
│   │   │   └── company_profile.py
│   │   ├── compliance/
│   │   │   ├── rule_check.py
│   │   │   ├── suitability_check.py
│   │   │   └── disclosure.py
│   │   └── workflow/
│   │       ├── human_review.py
│   │       └── consultation_record.py
│   ├── llm/
│   │   ├── base.py
│   │   ├── client.py
│   │   ├── providers/
│   │   │   ├── openai_compatible.py
│   │   │   ├── anthropic.py
│   │   │   └── local.py
│   │   ├── embeddings.py
│   │   ├── output_parser.py
│   │   └── token_budget.py
│   ├── retrieval/
│   │   ├── chunking.py
│   │   ├── indexer.py
│   │   ├── retriever.py
│   │   ├── reranker.py
│   │   └── citations.py
│   ├── repositories/
│   │   ├── base.py
│   │   ├── tenant.py
│   │   ├── user.py
│   │   ├── profile.py
│   │   ├── product.py
│   │   ├── consultation.py
│   │   ├── document.py
│   │   ├── memory.py
│   │   ├── task.py
│   │   ├── report.py
│   │   ├── approval.py
│   │   └── audit.py
│   ├── infrastructure/
│   │   ├── database/
│   │   │   ├── session.py
│   │   │   ├── models.py
│   │   │   └── repositories/
│   │   ├── cache/
│   │   │   ├── redis.py
│   │   │   ├── locks.py
│   │   │   └── rate_limit.py
│   │   ├── vector_store/
│   │   │   ├── base.py
│   │   │   ├── chroma.py
│   │   │   ├── qdrant.py
│   │   │   └── milvus.py
│   │   ├── object_storage/
│   │   │   ├── base.py
│   │   │   ├── s3.py
│   │   │   └── local.py
│   │   ├── queue/
│   │   │   ├── celery_app.py
│   │   │   └── tasks.py
│   │   └── mcp/
│   │       ├── client.py
│   │       ├── server_registry.py
│   │       └── adapters.py
│   ├── observability/
│   │   ├── tracing.py
│   │   ├── metrics.py
│   │   ├── audit.py
│   │   └── redaction.py
│   └── utils/
│       ├── time.py
│       ├── hashing.py
│       ├── pagination.py
│       └── serialization.py
├── tests/
│   ├── unit/
│   │   ├── domain/
│   │   ├── application/
│   │   ├── agents/
│   │   ├── pipelines/
│   │   ├── tools/
│   │   └── finance_engine/
│   ├── integration/
│   │   ├── api/
│   │   ├── database/
│   │   ├── retrieval/
│   │   ├── queue/
│   │   └── mcp/
│   ├── compliance/
│   ├── security/
│   └── e2e/
├── migrations/
├── scripts/
│   ├── init_db.py
│   ├── seed_rules.py
│   ├── ingest_documents.py
│   ├── rebuild_index.py
│   └── run_worker.py
├── configs/
│   ├── logging.yaml
│   ├── tools.yaml
│   ├── pipelines.yaml
│   └── compliance_rules/
├── docs/
│   ├── api.md
│   ├── data-model.md
│   ├── operations.md
│   └── security.md
├── pyproject.toml
├── alembic.ini
├── Dockerfile
├── docker-compose.yml
├── .dockerignore
├── .env.example
└── README.md
```

## 4. 分层职责与依赖规则

### 4.1 `api`

负责路由、HTTP 参数、鉴权依赖、Pydantic schema、状态码和响应转换。禁止直接访问数据库、Redis、向量库、LLM 或 MCP。

### 4.2 `application`

负责业务用例、事务边界、幂等控制和状态转换。例如创建咨询、追加消息、上传文档、执行适当性检查、提交人工复核。

### 4.3 `domain`

负责领域实体、值对象、枚举、状态转换和不依赖基础设施的业务规则。禁止导入 FastAPI、SQLAlchemy、Redis、LLM SDK。

### 4.4 `agents`

负责意图识别、上下文组装、结构化 Agent 协作和最终表达。Agent 不得持有数据库连接、密钥或外部服务客户端，只能生成符合契约的 Tool Call。

### 4.5 `pipelines`

负责定义和执行有边界的金融任务流程。Pipeline 只能通过 Tool Gateway 调工具，必须产生结构化输出和审计事件。

### 4.6 `tools`

负责原子能力、工具契约、工具选择、网关、可靠性和 Guardrail。金融计算工具必须是纯函数或可重放服务，不能在内部调用 LLM 生成数字。

### 4.7 `repositories`

负责抽象数据访问接口。Repository 不做 Agent 编排、合规判断或自然语言生成。

### 4.8 `infrastructure`

负责 PostgreSQL、Redis、对象存储、向量库、队列和 MCP 协议的具体实现。替换基础设施时，上层只依赖抽象接口。

### 4.9 `observability`

负责 Trace、Metrics、结构化日志、脱敏和 Audit。审计写入失败必须告警，并根据业务策略阻断“无审计完成”的高风险咨询。

### 4.10 依赖方向

```text
api -> application -> domain
application -> agents / pipelines / repositories / infrastructure interfaces
agents -> llm interfaces / tools interfaces / domain
pipelines -> agents / tools / domain
tools -> infrastructure interfaces / domain
repositories -> domain
infrastructure -> repositories and external systems
observability <- all layers through narrow interfaces
domain -> no framework or external service
```

禁止以下路径：

- `api -> database`。
- `api -> llm`。
- `agent -> concrete provider`。
- `agent -> external HTTP/database/filesystem`。
- `domain -> ORM/Pydantic API schema`。
- `pipeline -> concrete MCP server`。
- `memory/vector store -> become authoritative business database`。

## 5. 领域模型与状态机

### 5.1 核心实体字段

所有业务实体必须至少包含 `id`、`tenant_id`、`created_at`、`updated_at`、`version` 和审计关联字段；跨租户查询必须默认拒绝。

| 实体 | 关键字段 | 权威存储 |
|---|---|---|
| `Tenant` | `id`, `name`, `status`, `policy_version` | PostgreSQL |
| `User` | `id`, `tenant_id`, `subject_id`, `roles`, `status` | PostgreSQL |
| `UserProfile` | `risk_level`, `horizon`, `liquidity_need`, `source`, `confirmed_at`, `profile_version` | PostgreSQL |
| `RiskProfile` | `risk_score`, `loss_tolerance`, `experience`, `assessment_version`, `expires_at` | PostgreSQL |
| `FinancialProduct` | `product_type`, `risk_level`, `complexity`, `fees`, `liquidity`, `source_version` | PostgreSQL |
| `Conversation` | `user_id`, `summary`, `last_message_at`, `memory_version` | PostgreSQL + Redis |
| `ConsultationCase` | `intent`, `risk_level`, `status`, `question`, `answer_id` | PostgreSQL |
| `PipelineExecution` | `pipeline_id`, `version`, `status`, `input_ref`, `output_ref` | PostgreSQL |
| `Document` | `object_key`, `sha256`, `source`, `authorization_scope`, `status` | PostgreSQL + Object Storage |
| `Evidence` | `document_id`, `object_version`, `page`, `sheet`, `section_path`, `text_ref` | PostgreSQL |
| `MemoryRecord` | `kind`, `content_ref`, `source`, `confidence`, `confirmation_status`, `valid_from`, `valid_to` | PostgreSQL |
| `Task` | `task_type`, `status`, `attempts`, `error_type`, `result_ref` | PostgreSQL + Redis |
| `Report` | `case_id`, `version`, `status`, `object_key`, `citation_refs` | PostgreSQL + Object Storage |
| `AuditEvent` | `trace_id`, `event_type`, `actor`, `payload_ref`, `prev_hash`, `event_hash` | PostgreSQL + archive |
| `ApprovalRequest` | `case_id`, `risk_level`, `required_role`, `status`, `decision` | PostgreSQL |

### 5.2 画像可信度规则

画像字段必须记录：

- `source_type`: `user_explicit`, `questionnaire`, `human_confirmed`, `model_inferred`, `external_data`。
- `confidence`。
- `confirmation_status`: `pending`, `confirmed`, `rejected`, `expired`。
- `effective_at`、`expires_at`。
- `supersedes`。
- `source_event_id`。

`model_inferred` 且未确认的画像只能用于辅助上下文和追问，不能单独驱动适当性判断、强投资建议或硬性投资限制。

### 5.3 咨询状态机

| 状态 | 允许前置状态 | 触发者 | 用户确认 | 人工审批 | 可返回部分结果 |
|---|---|---|---|---|---|
| `received` | 无 | API | 否 | 否 | 否 |
| `classified` | `received` | Router | 否 | 否 | 否 |
| `clarification_required` | `classified` | Router/Application | 是 | 否 | 仅澄清问题 |
| `compliance_precheck` | `classified`/`clarification_required` | Application | 视风险 | 否 | 否 |
| `executing` | `compliance_precheck` | Pipeline | 否 | 否 | 是，非最终结论 |
| `waiting_confirmation` | `executing` | Gate | 是 | 否 | 可返回已验证事实 |
| `human_review` | `executing`/`waiting_confirmation` | Compliance | 否 | 是 | 仅返回审核中 |
| `compliance_postcheck` | `executing`/`human_review` | Compliance | 否 | 视风险 | 否 |
| `completed` | `compliance_postcheck` | Application | 否 | 否 | 是 |
| `partial_success` | `executing` | Application | 否 | 视风险 | 是，必须披露缺失 |
| `blocked` | 任意可阻断状态 | Guardrail/Compliance | 否 | 否 | 只返回阻断原因 |
| `failed` | 任意执行状态 | System | 否 | 否 | 仅结构化错误 |
| `cancelled` | 未完成状态 | User/Application | 否 | 否 | 否 |
| `expired` | `waiting_confirmation`/`human_review` | Scheduler | 否 | 否 | 否 |

所有状态变化必须写入 `AuditEvent`，并使用乐观锁或数据库条件更新防止并发覆盖。

## 6. API 规范

### 6.1 版本化路由

所有业务接口使用 `/api/v1` 前缀。`/health/live` 只判断进程存活，`/health/ready` 检查必需依赖是否可用。管理、审计和内部评测接口必须单独鉴权，不能与公开客服接口共用匿名访问策略。

### 6.2 v1 API

| 方法 | 路径 | 用途 | 幂等要求 |
|---|---|---|---|
| `GET` | `/health/live` | 存活检查 | 无 |
| `GET` | `/health/ready` | 依赖就绪检查 | 无 |
| `POST` | `/api/v1/consultations` | 创建咨询案例 | `Idempotency-Key` |
| `GET` | `/api/v1/consultations/{case_id}` | 查询咨询状态和结果 | 无 |
| `POST` | `/api/v1/consultations/{case_id}/messages` | 追加问题并执行 | `Idempotency-Key` |
| `POST` | `/api/v1/consultations/{case_id}/confirm` | 用户确认 | `Idempotency-Key` |
| `POST` | `/api/v1/consultations/{case_id}/cancel` | 取消任务 | `Idempotency-Key` |
| `GET` | `/api/v1/tasks/{task_id}` | 查询异步任务 | 无 |
| `POST` | `/api/v1/documents` | 上传原始资料 | 文件哈希幂等 |
| `GET` | `/api/v1/documents/{document_id}` | 查询文档和索引状态 | 无 |
| `POST` | `/api/v1/knowledge/search` | 检索授权知识 | 无 |
| `GET` | `/api/v1/products` | 产品查询 | 无 |
| `GET` | `/api/v1/products/{product_id}` | 产品详情 | 无 |
| `GET` | `/api/v1/users/me/profile` | 查询当前用户画像 | 无 |
| `PUT` | `/api/v1/users/me/profile` | 更新已确认画像 | `If-Match` |
| `POST` | `/api/v1/suitability/check` | 适当性检查 | `Idempotency-Key` |
| `GET` | `/api/v1/reports/{report_id}` | 查询报告 | 无 |
| `GET` | `/api/v1/audit/{case_id}` | 查询授权审计摘要 | 无 |

### 6.3 统一响应模型

```python
class ApiResponse(BaseModel, Generic[T]):
    request_id: str
    trace_id: str
    data: T | None = None
    warnings: list[WarningItem] = []
    citations: list[Citation] = []
    compliance: ComplianceSummary | None = None
    task: TaskSummary | None = None
    error: ApiError | None = None
```

实际代码中必须使用 `Field(default_factory=list)`，禁止使用可变对象作为默认值。

### 6.4 统一错误码

```text
INVALID_ARGUMENT
UNAUTHENTICATED
PERMISSION_DENIED
TENANT_SCOPE_VIOLATION
NOT_FOUND
IDEMPOTENCY_CONFLICT
STALE_DATA
INSUFFICIENT_DATA
DATA_SOURCE_CONFLICT
COMPLIANCE_BLOCKED
HUMAN_REVIEW_REQUIRED
USER_CONFIRMATION_REQUIRED
TOOL_TIMEOUT
TOOL_UNAVAILABLE
RATE_LIMITED
TASK_NOT_FOUND
INTERNAL_ERROR
```

错误响应不得包含堆栈、密钥、数据库连接信息或供应商内部错误细节。

## 7. Agent、Pipeline、Tool 和 Skill 契约

### 7.1 `RouterResult`

```json
{
  "primary_intent": "portfolio_diagnosis",
  "secondary_intents": ["risk_assessment", "macro_analysis"],
  "confidence": 0.86,
  "requires_clarification": false,
  "requires_computation": true,
  "requires_retrieval": true,
  "requires_user_profile": true,
  "requires_compliance_review": true,
  "risk_level": "high",
  "candidate_pipelines": ["portfolio_diagnosis@1.0.0"],
  "trace_id": "trace_xxx"
}
```

置信度策略：

- `>= 0.80`：可以进入已配置 Pipeline，但高风险场景仍必须合规检查。
- `0.55 - 0.79`：进入澄清流程。
- `< 0.55`：不强行路由，要求补充信息或转人工。

### 7.2 `PipelineManifest`

```json
{
  "pipeline_id": "portfolio_diagnosis",
  "version": "1.0.0",
  "supported_intents": ["portfolio_diagnosis", "risk_assessment"],
  "required_inputs": ["question", "user_profile", "portfolio_ref"],
  "optional_inputs": ["investment_horizon", "benchmark"],
  "required_skills": ["portfolio_review@1.0.0"],
  "allowed_tools": ["portfolio_data@1.0.0", "portfolio_risk@1.0.0"],
  "blocked_tools": ["trade_execution"],
  "risk_level": "high",
  "output_schema": "PortfolioDiagnosisResult",
  "timeout_seconds": 45,
  "audit_required": true
}
```

### 7.3 `ToolManifest`

```json
{
  "tool_id": "market_quote",
  "version": "1.0.0",
  "mcp_server": "financial-data-server",
  "input_schema": "MarketQuoteInput",
  "output_schema": "MarketQuoteOutput",
  "risk_level": "L0",
  "side_effect": "read_only",
  "reversible": true,
  "requires_confirmation": false,
  "requires_approval": false,
  "timeout_seconds": 5,
  "cache_policy": {"enabled": true, "ttl_seconds": 30},
  "retry_policy": {"max_attempts": 2, "idempotent_only": true},
  "circuit_breaker_policy": {"failure_threshold": 5, "cooldown_seconds": 30},
  "fallback_policy": {"allow_authorized_cache": true, "allow_stale_data": false}
}
```

风险等级：

- `L0`：只读查询、检索和确定性计算。
- `L1`：缓存、草稿和非正式分析记录。
- `L2`：修改配置、生成订单草稿或发送外部通知，必须用户确认。
- `L3`：交易、资金、删除和不可逆变更，默认禁止并要求人工审批。

### 7.4 `GuardrailDecision`

```json
{
  "decision": "allow | block | require_confirmation | require_approval | degrade",
  "rule_ids": ["personalized_advice_requires_profile"],
  "reason": "用户风险画像未确认",
  "required_action": "collect_confirmed_risk_profile",
  "trace_id": "trace_xxx",
  "audit_event_id": "audit_xxx"
}
```

### 7.5 `FinanceResult`

```json
{
  "status": "completed",
  "metric": "target_price_dcf",
  "value": 128.4,
  "currency": "USD",
  "unit": "per_share",
  "period": "FY2025-FY2030",
  "formula_version": "dcf_v1.0.0",
  "assumptions": {"wacc": 0.092, "terminal_growth": 0.025},
  "data_sources": ["filing_001", "market_data_001"],
  "warnings": [],
  "confidence": "medium",
  "calculated_at": "2026-08-22T10:00:00Z"
}
```

数据不足必须返回 `status=insufficient_data`、`missing_fields` 和用户可见提示，禁止自动填充未经批准的关键假设。

### 7.6 `SupervisorPlan`（schema 驱动调用图）

多 Agent 编排采用**确定性 DAG 调用图**，不是自由群聊。Supervisor 先产出计划，再按图逐个执行；Agent 之间只传结构化对象，不传自然语言。

```json
{
  "plan_id": "plan_001",
  "case_id": "case_001",
  "trace_id": "trace_xxx",
  "plan_version": "1.0.0",
  "nodes": [
    {"step_id": "data", "agent": "data_agent", "input_refs": [], "output_schema": "DataPackage"},
    {"step_id": "model", "agent": "modeling_agent", "input_refs": ["data"], "output_schema": "ValuationPackage"},
    {"step_id": "risk", "agent": "risk_agent", "input_refs": ["data", "model"], "output_schema": "RiskAssessment"},
    {"step_id": "debate", "agent": "bull_bear_agent", "input_refs": ["data", "model", "risk"], "output_schema": "InvestmentDebate"}
  ],
  "final_agent": "advisor",
  "edges": [["data", "model"], ["model", "risk"], ["risk", "debate"], ["debate", "advisor"]]
}
```

约束：

- Supervisor 生成的 DAG 必须通过 schema 校验；节点数量上限为 5。
- 每个 Agent 只能消费 `input_refs` 声明的结构化结果，不允许私自访问其他节点或外部系统。
- 节点失败或超时沿 DAG 传导：关键节点失败阻断结论，非关键节点失败保留部分结果并披露缺失。
- Agent 运行期不得修改 DAG；新增专家能力通过扩展 `agents/roles/` 注册，而不是让 Agent 自由协商。
- 大多数咨询（产品解释、知识问答）走单模型 workflow，只有 valuation/portfolio 场景才启用多 Agent DAG。

## 8. 咨询主流程

```text
1. API 验证身份、租户、请求大小和 Idempotency-Key
2. 创建 ConsultationCase 和初始 AuditEvent
3. 读取已确认画像、会话工作记忆和授权上下文
4. Router 生成 RouterResult
5. 置信度不足则进入 clarification_required
6. Compliance Pre-check 判断风险和可用工具
7. Pipeline Registry 选择版本化 Pipeline
8. Tool Router 根据权限、Skill、数据范围和风险选择最小工具集合
9. Tool Gateway 执行参数校验、权限、缓存、熔断、重试和调用路径 Guardrail
10. Data Quality Gate 检查来源、时效、币种、单位、期间和完整性
11. Finance Engine 生成可重放的确定性结果
12. 专家 Agent 只消费结构化数据、计算结果和证据引用
13. Advisor/Synthesis Agent 生成结构化回答草稿
14. Compliance Post-check 检查越界表达、风险披露、引用和画像约束
15. 需要确认或人工审批时暂停，不返回最终建议
16. 完成后写入 AuditEvent，返回 answer、warnings、citations 和 compliance
17. 仅把满足来源、权限、确认和有效期条件的记忆异步写入 PostgreSQL
18. 向量索引异步更新；失败时重试并告警，不影响 PostgreSQL 权威记录
```

## 9. 合规规则与人工复核

### 9.1 必须阻断或改写的表达

至少覆盖：

- “保证收益”。
- “稳赚不赔”。
- “一定上涨/一定下跌”。
- “无风险”。
- 未有用户画像时的确定性买卖指令。
- 基于非公开重大信息的交易建议。
- 把历史业绩作为未来收益承诺。
- 将一般信息表达为税务或法律专业意见。

### 9.2 必须触发合规审查的场景

- 个性化买卖建议。
- 组合调仓、减仓或再平衡建议。
- 高风险或复杂金融产品。
- 用户画像、风险等级或投资期限不足。
- 税务、法律、内幕信息和收益保证问题。
- 数据来源不完整、过期或存在冲突。
- 任何 L2/L3 工具调用。

### 9.3 合规决策顺序

```text
规则引擎硬规则
  -> 用户/租户/产品适当性查询
  -> LLM 辅助敏感意图识别
  -> Tool Call 前 Guardrail
  -> 输出后规则扫描
  -> 高风险人工审批
```

LLM Judge 只能作为辅助检测和评测手段，不能替代确定性合规规则或人工审批。

### 9.4 合规规则可执行 schema

合规规则以声明式、可测试的确定性规则为主，存放在 `configs/compliance_rules/`。每条规则必须满足：

```json
{
  "rule_id": "guaranteed_return_ban",
  "version": "1.0.0",
  "category": "prohibited_expression",
  "priority": 10,
  "severity": "block",
  "description": "禁止保证收益/保本/稳赚等确定性收益承诺",
  "trigger": {
    "type": "keyword_or_llm",
    "patterns": ["保证收益", "稳赚", "保本", "guaranteed return", "risk-free"],
    "llm_hint": "识别用户请求或草稿中隐含收益承诺的表达"
  },
  "action": "block",
  "required_disclosures": [],
  "rewrite_hint": "改写为风险提示：收益不确定，不构成任何承诺",
  "test_cases": [
    {"input": "保证我一年赚 10%", "expected": "block"},
    {"input": "这个产品历史收益不错，未来大概率上涨", "expected": "rewrite"}
  ]
}
```

规则引擎执行契约：

- `action` 语义固定为 `block | rewrite | require_disclosure | require_human | require_profile`。
- 多条规则命中时按 `priority` 从高到低处理，`block` 优先级最高。
- `trigger.type=keyword_or_llm` 时，命中关键词即可确定性判定；LLM 只用于补充识别，不能否决硬规则。
- 每条规则必须带 `test_cases`，规则变更需跑通全部规则测试与回归门禁后才可晋级。
- 规则版本化；审计记录实际命中的 `rule_id` 和 `version`。

## 10. 数据与基础设施

### 10.1 存储职责

| 组件 | 职责 | 约束 |
|---|---|---|
| PostgreSQL | 用户、租户、产品、会话、画像、任务、报告、记忆元数据、审计 | 唯一权威数据源 |
| Redis | 工作记忆、摘要、任务状态、限流、锁、短期缓存 | 不能保存唯一业务记录 |
| Object Storage | 原始 PDF/Excel/研报、报告和大型工具结果 | 保存版本、哈希和授权范围 |
| Qdrant Cloud | 持久化租户向量索引 | 通过 `VectorStore` 接口接入，集合维度必须匹配 embedding 模型 |
| Celery + Redis | 文档解析、索引、报告、评测和数据同步 | 任务必须可重试、可观测 |

### 10.2 多租户隔离

所有业务表必须包含 `tenant_id`，Repository 默认注入当前租户条件。对象存储 key 和 Redis key 必须包含租户和主体范围，例如：

```text
tenant/{tenant_id}/user/{user_id}/document/{document_id}/version/{version}
tenant:{tenant_id}:user:{user_id}:conversation:{conversation_id}
```

向量检索流程必须是：

```text
租户/权限/项目/实体/状态硬过滤
  -> 向量召回
  -> PostgreSQL 回查
  -> 权限、版本、有效期复核
  -> 重排序
  -> 生成引用
```

不能把租户和权限交给向量相似度判断。

### 10.3 文档和证据

每个证据必须能通过以下字段定位原文：

- `document_id`。
- `object_version`。
- `page`。
- `sheet`。
- `cell_range`。
- `section_path`。
- `sha256`。

替换原文件时创建新版本，不能覆盖支撑历史建议的旧版本。

### 10.4 数据供应商字段级契约（调研产出）

数据供应商尚未确定，本契约是**接入任何数据源前必须填写的模板**，也是 Data Quality Gate 和 Finance Engine 的地基。未填写契约的 source 禁止进入生产路由。

```yaml
data_source_id: market_quote
provider: <待定: Wind / iFinD / Choice / Tushare Pro / ...>
authorization_scope: <license 及可分发边界>
data_types: [equity_quote, corporate_actions]
update_frequency: intraday   # intraday | eod | delayed
history_available: true
fields:
  - name: close_price
    type: decimal
    currency: CNY
    unit: per_share
    adjustment: forward_adjusted   # 复权处理策略
    source_period: T-1
corporate_actions:
  splits: true
  dividends: true
  adjusted: true
market_calendar:
  open: "09:30+08:00"
  close: "15:00+08:00"
  holidays: csrc
fx_policy:
  rate_source: <待定>
  as_of: trade_date
conflict_resolution:
  order: [authorized_primary, authorized_secondary, manual_review]
  rule: prefer_latest_as_of_then_primary_source
retention: <保留策略>
```

每个数据源契约必须由数据负责人与合规确认；Finance Engine 只能消费已冻结契约的字段，Data Quality Gate 按契约校验来源、授权、时效、币种、单位、期间、复权与多源冲突。

## 11. Finance Engine v1

### 11.1 范围

- DCF。
- WACC。
- 可比公司估值。
- 组合集中度和行业暴露。
- Bull/Base/Bear 情景分析。

### 11.2 统一计算要求

每个计算模块必须定义：

- 输入 Pydantic schema。
- 输出 `FinanceResult` schema。
- `formula_version`。
- 单位、币种和报告期。
- 数据源和数据时间。
- 缺失字段、过期字段和冲突字段处理。
- 公式基准测试和边界测试。
- 结果重放命令或函数。

关键数字必须使用 `Decimal` 或明确的高精度计算策略，避免使用无约束的二进制浮点数直接作为财务结果。

### 11.3 数据质量 Gate

至少检查：

- 来源是否授权。
- 数据是否过期。
- 财务期间是否匹配。
- 币种和单位是否一致。
- 拆股、分红和复权是否处理。
- 必填字段是否存在。
- 多源数据是否冲突。
- 用户持仓是否完整。

质量不足时只能：

- 返回已验证的部分结果并披露缺失。
- 要求用户补充信息。
- 阻断相关结论。

## 12. 审计与可观测性

### 12.1 链路标识

```text
request_id
trace_id
case_id
pipeline_execution_id
tool_call_id
audit_event_id
answer_id
```

同一次咨询中的 Agent、Pipeline、Tool、Guardrail、MCP、Finance Engine 和最终回答必须复用同一 `trace_id`。

### 12.2 审计事件

至少记录：

- 用户输入和请求主体。
- 租户、用户、角色和数据授权范围。
- Router 结果和置信度。
- 画像字段、来源、版本和确认状态。
- Pipeline、Skill、Prompt 和模型版本。
- Tool/MCP Server 版本、参数引用和结果引用。
- 缓存命中、重试、熔断和 fallback。
- 数据质量 Gate 结果。
- Finance Engine 公式、假设和输出。
- Guardrail 和 Compliance 决策。
- 用户确认、人工审批和人工接管。
- 最终回答、风险披露和引用。

敏感原文应按访问权限保存或脱敏，AuditEvent 中优先保存引用和哈希，避免把密钥或不必要的个人敏感信息写入普通日志。

#### 12.2.1 不可变性与哈希链

- `AuditEvent` 只允许 `INSERT`，禁止 `UPDATE` / `DELETE`；历史事件不可覆盖。
- `event_hash = SHA256(prev_event_hash + canonical_json(event))`，`prev_hash` 指向同一 `case_id` 内前一条事件。
- 首条事件 `prev_hash` 为 `case_id` 的 genesis 哈希。
- 提供 `scripts/verify_audit_chain.py`，可重放并校验整条链；哈希断裂必须告警。
- PoC 级用单表 + 哈希链即可满足试点审计；生产级 WORM/加密/归档在试点通过后再补。
- 审计写入失败时：`risk_level=high` 的咨询阻断完成；其余告警后允许降级，但必须留失败记录。

### 12.3 指标

- 请求量、成功率、错误率。
- P50/P95/P99 延迟。
- LLM Token、费用和模型分布。
- Tool 成功率、超时率、重试率、fallback 率。
- MCP Server 熔断状态。
- RAG Recall@K 和引用准确率。
- Finance Engine 数据不足率和计算失败率。
- 合规阻断率、人工升级率和确认等待时长。
- 数据供应商新鲜度、冲突率和错误率。
- 任务队列积压和死信数量。
- 审计写入失败数量。

### 12.4 PoC 级成本与容量基线

- 每个 intent 声明模型档位：`rule_only`（零 LLM）/ `small`（轻量模型）/ `large`（复杂综合）。
- 单 case 的 token 预算与工具调用上限：默认 token ≤ 8K、工具调用 ≤ 12 次，超出即降级或澄清。
- 租户级并发与配额：试点阶段单租户即可，但保留 `tenant` 配额字段。
- 多 Agent 仅在 valuation/portfolio 场景启用，节点 ≤ 5，其余用单模型 workflow。
- 用 `span.model_request_end` 累计成本与 token；PoC 只打点观测，不建生产级预算告警。

## 13. 安全与权限

### 13.1 身份认证

生产环境使用企业 OIDC/OAuth2 或等价 SSO。开发环境可以使用 JWT，但不得把开发密钥带入生产。

请求上下文至少包含：

```text
subject_id
tenant_id
organization_id
roles
scopes
data_entitlements
trace_id
```

### 13.2 权限策略

同时使用：

- RBAC：角色能做什么。
- ABAC：当前主体、租户、产品、地区、数据范围和风险等级是否允许。
- Tool risk policy：L0/L1/L2/L3 是否需要确认或审批。

权限检查必须在 API、Repository、向量检索、对象存储和 Tool Gateway 关键边界重复执行，不能只依赖前端或单个 API 检查。

### 13.3 数据安全

- Secret 通过 Secret Manager 或运行时环境注入。
- `.env` 不进入 Git 和 Docker 镜像。
- 数据库、Redis、对象存储和 MCP 连接使用 TLS 或受控内网。
- 日志和错误响应必须脱敏。
- PII、持仓和风险画像按最小权限访问。
- 定义数据留存、删除、导出和审计访问策略。

## 14. 开发顺序

> 开发顺序已按「两批闭环」重排。第一批（Phase 1–3 + Phase 5/6 中不依赖真实行情的部分）立即开工；第二批（Phase 4 的 Finance Engine、画像/适当性、组合诊断、人工复核、报告）待数据供应商契约冻结后再真开工。**Phase 0：数据供应商调研** 与第一批并行。

### Phase 0：数据供应商调研（并行，不阻塞第一批）

- 调研并冻结字段级数据契约（见 10.4）。
- 冻结 Finance Engine 输入/输出 schema 与 golden cases（用公开财报样本先做基准）。

### Phase 1：工程骨架

- 创建 `app/main.py` 和 FastAPI lifespan。
- 创建配置、日志、异常、Trace 和健康检查。
- 创建 Pydantic schema、依赖注入和版本化 Router。
- 配置 Ruff、Mypy、Pytest 和 pre-commit。

### Phase 2：数据和领域基础

- 创建 PostgreSQL Session、SQLAlchemy 模型和 Alembic。
- 创建 Tenant、User、Profile、Product、Consultation、Task、Audit 模型。
- 创建 Repository 接口和租户过滤。
- 创建 Redis、对象存储和 VectorStore 抽象。

### Phase 3：咨询用例和状态机

- 创建 Consultation Service。
- 实现咨询状态转换和乐观锁。
- 实现 Idempotency-Key。
- 实现任务、确认、取消和人工复核。

### Phase 4：金融能力

- 实现 Finance Engine 输入输出契约。
- 实现 DCF、WACC、Comps、组合风险和情景分析。
- 实现 Data Quality Gate。
- 为每个模块建立基准数据和回归测试。

### Phase 5：Agent、Tool 和合规

- 实现 Intent Registry 和 Router。
- 实现 Pipeline Registry。
- 实现 Tool Registry、Tool Contract Validator 和 Gateway。
- 实现 MCP Client/Adapter。
- 实现超时、重试、熔断、缓存、fallback 和 Guardrail。
- 实现 Compliance Pre-check/Post-check 和人工审批。

### Phase 6：RAG、记忆和报告

- 实现对象存储和文档解析。
- 实现 Parent-Child 分块、索引、检索、重排和引用。
- 实现 Redis 工作记忆、PostgreSQL 权威记忆和异步向量索引。
- 实现报告生成和证据回溯。

### Phase 7：生产化

- 完成多租户、OIDC、审计后台和数据留存。
- 完成 OpenTelemetry、Prometheus 和告警。
- 完成 Docker API/Worker 镜像。
- 完成备份恢复、故障演练和发布门禁。

## 15. 测试与验收

### 15.1 单元测试

- Domain 实体和状态转换。
- 金额、币种、期间和引用值对象。
- DCF/WACC/Comps/组合风险计算。
- 合规规则和敏感表达检测。
- Tool Manifest 校验。
- Router 置信度和澄清策略。
- Memory 可信度和确认策略。

### 15.2 集成测试

- FastAPI 路由和统一错误响应。
- PostgreSQL Repository 和迁移。
- Redis TTL、锁、幂等和任务状态。
- 对象存储上传、版本和哈希。
- VectorStore 硬过滤和回查。
- MCP Client/Server 协议错误转换。
- Celery 任务重试和死信。

### 15.3 安全和合规测试

- 不同租户不能召回彼此数据。
- 未确认画像不能用于强适当性判断。
- 未授权产品和文档不能进入上下文。
- 保证收益和保本表达必须阻断或改写。
- L2 工具未确认不得执行。
- L3 工具始终进入审批或阻断。
- Prompt Injection 和恶意文档不能绕过 Tool Gateway。
- 错误响应不能泄露密钥、堆栈和内部地址。

### 15.4 金融和 RAG 测试

- Finance Engine 基准结果和边界值。
- 缺失字段、过期数据和多源冲突。
- 币种、单位和财务期间错误。
- 引用能定位到原文件版本和页码/表格位置。
- 检索结果先硬过滤再召回。
- Qdrant Cloud 索引删除后可按 PostgreSQL 权威文档重建。

### 15.5 端到端验收案例

| 案例 | 必须验证 |
|---|---|
| “请解释某基金的主要风险和费用” | 产品事实、来源、更新时间和风险说明 |
| “我持有 AAPL、NVDA、TSLA，近期是否需要降风险” | 画像、组合计算、数据质量、合规和条件化表达 |
| “帮我分析英伟达是否估值过高” | DCF/Comps、公式版本、假设、警告和引用 |
| “总结这份 10-K 的主要风险” | 文档版本、章节引用和证据准确性 |
| “保证我一年赚 10%” | 阻断保证收益并返回合规说明 |
| MCP Server 超时 | 超时记录、熔断、fallback 或可解释失败 |
| 审计写入失败 | 高风险咨询阻断或告警，不得无记录完成 |

## 16. Docker 和部署规格

### 16.1 镜像职责

- `api`：运行 FastAPI，只提供 HTTP 服务。
- `worker`：运行 Celery 文档、索引、报告和评测任务。
- `scheduler`：可选，运行定时数据同步、过期处理和索引维护。

API 和 Worker 可以共用依赖基础镜像，但必须使用不同启动命令。

### 16.2 Dockerfile 要求

- 使用 Python 3.11 或 3.12 slim 基础镜像。
- 多阶段构建，生产镜像不包含测试缓存和源码控制目录。
- 使用非 root 用户。
- 依赖文件先复制并安装，利用构建缓存。
- Secret 通过运行时环境注入。
- 提供 `/health/live` 健康检查。
- 支持优雅关闭，任务 Worker 不丢失正在处理的任务。

生产启动命令示例：

```text
gunicorn app.main:app -k uvicorn.workers.UvicornWorker -w 4 -b 0.0.0.0:8000
```

Worker 启动命令示例：

```text
celery -A app.infrastructure.queue.celery_app worker --loglevel=INFO
```

### 16.3 Compose 服务边界

开发环境至少包含：

- `api`
- `worker`
- `postgres`
- `redis`
- `object-storage`，可使用 MinIO
- `vector-store`，内部试点使用 Qdrant Cloud；离线测试使用 memory 替身
- `prometheus`

生产环境不得把本地文件、SQLite 或测试用 memory vector store 作为唯一数据源。Docker Compose 适合开发和单机验证，生产建议使用云托管数据库、对象存储、Qdrant Cloud 和 Kubernetes 或等价编排平台。

### 16.4 数据迁移和发布顺序

```text
构建并扫描镜像
  -> 运行数据库兼容迁移
  -> 部署 API/Worker
  -> readiness 检查
  -> 执行回归和合规门禁
  -> 切换流量
  -> 观察指标和审计写入
```

数据库迁移必须向后兼容至少一个发布周期，不能在 API 仍使用旧版本时删除旧字段。

## 17. 配置基线

`.env.example` 至少包含：

```text
APP_ENV=development
API_HOST=0.0.0.0
API_PORT=8000
DATABASE_URL=postgresql+psycopg://app:password@postgres:5432/financial_agent
REDIS_URL=redis://redis:6379/0
OBJECT_STORAGE_ENDPOINT=http://minio:9000
OBJECT_STORAGE_BUCKET=financial-agent
VECTOR_STORE_BACKEND=chroma
VECTOR_STORE_URL=http://chromadb:8000
LLM_PROVIDER=openai_compatible
LLM_MODEL=provider-model
LLM_API_KEY=replace-at-runtime
JWT_ISSUER=replace-at-runtime
JWT_AUDIENCE=financial-agent
AUDIT_RETENTION_DAYS=2555
DEFAULT_REQUEST_TIMEOUT_SECONDS=60
```

生产配置必须由 Secret Manager、容器平台 Secret 或等价机制提供。文档示例不得使用真实密钥。

## 18. 开工完成标准

进入业务编码前，以下条件必须满足：

- `app/main.py`、v1 Router、依赖注入和健康检查可启动。
- 核心领域对象和状态机已经定义并通过单元测试。
- API Schema、错误码和幂等约束已经固定。
- Tenant、User、Profile 和 Audit 的数据模型已经确定。
- Finance Engine v1 输入、输出、公式版本和基准数据已经确定。
- Tool/Skill/Pipeline/Agent 契约已经可以被 schema 校验。
- Compliance Gate 和人工复核触发条件已经确认。
- PostgreSQL、Redis、对象存储和向量存储职责没有重叠歧义。
- Docker API/Worker 启动命令和 Compose 依赖已经明确。
- 最小端到端案例和合规红线案例已经进入测试集。
- 开工前冻结的最小集已落地：数据供应商字段级契约模板（10.4）、合规规则可执行 schema（9.4）、审计 append-only 哈希链（12.2.1）、LLM 层仅 `openai_compatible`（19）、多 Agent 调用图（7.6）。

## 19. 设计决策记录

| 决策 | 结论 | 原因 |
|---|---|---|
| Web 框架 | FastAPI | 异步接口、Pydantic schema、OpenAPI 和 Python Agent 生态 |
| 业务分层 | API + Application + Domain + Infrastructure | 控制依赖方向，便于测试和替换外部实现 |
| 生产权威库 | PostgreSQL | 事务、版本、权限、审计和可查询性 |
| 工作记忆 | Redis | TTL、并发、短期状态和锁 |
| 向量索引 | Qdrant Cloud；离线测试使用 memory 替身 | 索引可重建，模型或维度变更需显式新建集合并回填 |
| 异步队列 | Celery + Redis | 文档、报告、索引和评测任务需要重试与监控 |
| LLM 接入 | Provider 抽象；PoC 只实现 `openai_compatible`（国内合规 API），`anthropic`/`local` 留 stub | 中国大陆部署不假设海外直连，避免锁定单一供应商 |
| 工具执行 | Tool Gateway + MCP Client/Server | 统一权限、可靠性、审计和外部能力接入 |
| 合规判断 | 确定性规则为主，LLM 辅助，人工兜底 | 金融高风险判断不能只依赖生成模型 |
| 交易能力 | 首期禁止 | 降低不可逆副作用和合规风险 |

## 20. 对当前 EchoMind 代码的迁移说明

当前仓库中的 `api/main.py`、`agents/agent_orchestrator.py`、`memory/conversation_memory.py`、`mcp/tool_manager.py`、`mcp/knowledge_base.py`、`evaluation/evaluator.py` 和 `monitor/performance_monitor.py` 可以作为底座参考，但不能直接视为本规格已经实现。

迁移时应遵循：

1. 保留已有的 Redis 工作记忆、Qdrant Cloud 检索、Skill 加载、Tool schema 校验、缓存、熔断、fallback、监控和评测思路。
2. 将现有通用客服 Intent 替换为金融 Intent Registry。
3. 将现有通用 Agent 路由迁移为 Router、Pipeline 和专家 Agent 契约。
4. 将 `mcp/tool_manager.py` 定位为 Tool Gateway/Reliability Layer 参考，不把它误认为完整 MCP Server。
5. 新增 PostgreSQL、对象存储、租户权限、Finance Engine、Compliance Gate 和 Audit Trail。
6. API 层从单文件入口拆分为版本化 endpoints、schemas、dependencies 和 application service。
7. 在删除或迁移既有功能前，先为新旧链路建立回归测试。

## 21. 参考实现顺序

第一批建议只提交以下可运行闭环：

```text
FastAPI health
  -> consultation create
  -> financial intent router
  -> product explanation pipeline
  -> knowledge retrieval with citation
  -> compliance post-check
  -> audit event persistence
  -> structured response
```

第二批加入：

```text
user profile
  -> suitability check
  -> portfolio diagnosis
  -> finance engine
  -> human review
  -> asynchronous report
```

在这两个闭环通过测试和评测门禁前，不应扩展交易、复杂衍生品、自动推荐或多套向量数据库。