# Financial Consultation Agent

一个面向金融咨询场景的 FastAPI 后端 PoC，强调确定性金融计算、授权资料检索、可追溯引用、合规检查和审计链。

> **项目状态：Local Development / Internal Pilot PoC**
> 当前版本不适合公网部署，也不构成投资、税务或法律意见。

## 项目定位

本项目参考金融 Agent 的模块化设计理念，将以下能力拆分为可替换的领域模块：

- 咨询意图路由和版本化 Pipeline；
- 产品说明、授权文档检索和引用；
- Qdrant 云向量检索与 OpenAI-compatible Embedding 接口；
- DCF、WACC、可比公司、情景分析和组合诊断；
- 确定性合规 pre-check / post-check；
- Tool Gateway、租户过滤、确认和人工复核；
- PostgreSQL、Redis、MinIO、Celery 和审计链基础设施。

关键原则：金融数字由确定性代码生成，LLM 只能用于意图理解、解释和表达，不能覆盖 Finance Engine 的结果。

## 已实现能力

- 产品信息解释和风险/费用说明；
- 文本文档上传、版本哈希和引用；
- 关键词 fallback 与 Embedding 检索；
- Qdrant 向量存储适配器和租户/状态/授权过期硬过滤；
- 可替换的 Embedding Provider，支持本地 hashing 和云端 OpenAI-compatible embedding API；
- DCF、WACC、可比公司、情景分析的 Decimal 计算结果；
- 组合集中度、行业暴露和人工复核状态；
- 合规规则 JSON 加载和确定性阻断/改写/人工复核；
- SHA-256 append-only 审计链；
- PostgreSQL/Redis/MinIO/Celery 的适配器和迁移基础；
- 开发模式 JWT/OIDC 边界和生产 fail-closed 配置校验；
- GitHub Actions 编译、测试和 Compose 配置校验。

## 明确不支持

- 自动下单、交易、资金划转或其他不可逆操作；
- 保证收益、保本或确定性涨跌结论；
- 未授权金融数据源；
- 将未确认用户画像作为唯一适当性依据；
- 具有法律效力的投资、税务或法律意见。

## 架构概览

```text
Client
  |
FastAPI API
  |
Application Services
  |
Consultation Workflow
  |-- Intent Router / Pipeline Registry
  |-- Compliance Gate / Tool Gateway
  |-- Retrieval / Embedding API / Qdrant Cloud
  |-- Deterministic Finance Engine
  |-- Advisor / Audit Chain
  |
PostgreSQL / Redis / MinIO / Celery
```

## 项目结构

```text
app/
  agents/          意图路由、Advisor、Supervisor 契约
  api/             FastAPI 路由和请求 schema
  application/     咨询、文档索引、组合诊断用例
  core/            配置、认证、异常和幂等
  data/            数据供应商协议和质量 Gate
  domain/          领域实体、状态和数值对象
  finance/         DCF、WACC、Comps、Scenario
  infrastructure/  PostgreSQL、Redis、对象、队列、向量存储
  llm/             LLM 和 Embedding Provider 抽象
  observability/   日志、指标和审计
  pipelines/       咨询、产品解释和合规流程
  repositories/    内存和 SQL 仓储
  tools/           合规、契约、可靠性和 Tool Gateway
configs/           合规规则和数据源契约
migrations/        PostgreSQL 迁移脚本
fixtures/          仅用于开发/测试的合成数据
tests/             单元、契约和边界测试
```

## 环境要求

- Python 3.11+
- Docker Desktop 或 Linux Docker Engine
- Docker Compose v2
- PostgreSQL、Redis、MinIO、Celery；
- Qdrant Cloud（运行时配置 URL 和 API key）；
- OpenAI-compatible embedding API（例如阿里云百炼，运行时配置模型、维度和 API key）；
- OpenAI-compatible LLM 服务（例如 DeepSeek，运行时配置模型和 API key）。

## 本地启动

以下命令从项目根目录执行；后端代码位于 `backend/`，前端代码位于 `frontend/`。

复制配置模板：

```bash
cp .env.example .env
```

安装 Python 依赖：

```bash
python -m pip install -e ".[test]"
```

启动本地服务：

```bash
cd ..
docker compose --env-file backend/.env up -d --build
```

默认地址：

| 服务 | 地址 |
|---|---|
| API | http://localhost:8010 |
| PostgreSQL | localhost:5433 |
| Redis | localhost:6380 |
| MinIO API | http://localhost:9002 |
| MinIO Console | http://localhost:9003 |
| Qdrant | configured cloud endpoint |
| Embedding API | configured OpenAI-compatible endpoint |

健康检查：

```bash
curl http://localhost:8010/health/live
curl http://localhost:8010/health/ready
```

默认 Compose 配置是本地开发配置，使用开发认证和合成数据。不要把这些端口暴露到公网。

## 模型和向量配置

`.env.example` 提供完整模板。核心配置如下：

```env
VECTOR_STORE_BACKEND=qdrant
VECTOR_STORE_URL=https://your-cluster.cloud.qdrant.io
QDRANT_COLLECTION=financial-agent-documents
QDRANT_API_KEY=replace-with-qdrant-api-key

EMBEDDING_PROVIDER=openai_compatible
EMBEDDING_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
EMBEDDING_API_KEY=replace-with-dashscope-api-key
EMBEDDING_MODEL=text-embedding-v3
EMBEDDING_DIMENSION=1024

LLM_PROVIDER=openai_compatible
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_API_KEY=replace-with-deepseek-api-key
LLM_MODEL=deepseek-v4-pro
```

Embedding 和 LLM 的地址与密钥应分开配置。Qdrant 集合维度必须与 Embedding 输出维度一致。模型和数据服务的授权、隐私和再分发条款需要在生产前单独确认。

## API 示例

创建咨询：

```bash
curl -X POST http://localhost:8010/api/v1/consultations \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: demo-consultation-1' \
  -d '{"question":"请解释示例基金的主要风险和费用"}'
```

主要路由：

- `GET /health/live`
- `GET /health/ready`
- `POST /api/v1/consultations`
- `GET /api/v1/consultations/{case_id}`
- `POST /api/v1/consultations/{case_id}/messages`
- `POST /api/v1/consultations/{case_id}/confirm`
- `POST /api/v1/consultations/{case_id}/cancel`
- `POST /api/v1/documents`
- `GET /api/v1/documents/{document_id}`
- `POST /api/v1/knowledge/search`
- `GET /api/v1/products`
- `POST /api/v1/suitability/check`
- `POST /api/v1/portfolio/diagnoses`
- `POST /api/v1/reports`
- `GET /api/v1/audit/{case_id}`

## 测试

```bash
python -m compileall -q app tests scripts
python -m pytest -q
```

CI 会执行依赖安装、编译、测试和 Compose 配置校验。需要真实数据库、Qdrant 或模型服务的测试应作为独立集成测试运行。

## 安全和隐私

- 不要提交 `.env`、API Key、JWT Secret、密码、私钥、HF Token 或真实用户金融数据；
- 生产环境必须使用 OIDC/JWT，关闭 `AUTH_DEV_MODE` 和内存 fallback；
- Qdrant、PostgreSQL、Redis、MinIO 不应直接暴露到公网；
- 租户和授权范围必须在服务端硬过滤；
- 金融数据供应商必须具备授权和再分发许可；
- 用户问题、文档、持仓和风险画像应按最小权限处理；
- 审计记录需要符合机构留存、访问和不可变归档策略；
- 发现漏洞请参阅 [SECURITY.md](SECURITY.md)，不要公开提交真实凭据。

## 生产状态

当前不是生产就绪系统。上线前至少还需要完成：

- 生产 OIDC/JWT、RBAC/ABAC、限流和租户授权；
- PostgreSQL、Redis、Qdrant、对象存储和 Celery 的生产级运行与恢复；
- API 与 Worker 共享同一持久向量后端；
- 真实授权金融数据供应商和字段级契约；
- Qdrant Cloud、embedding API 和 LLM endpoint 的正式模型、版本、成本和失败策略；
- Finance Engine 接入实际咨询 Pipeline，并通过专业人员复核 golden cases；
- PDF/Excel 解析、文档版本、页码/表格引用和异步报告；
- WORM/不可变审计归档、监控、告警、备份和恢复演练；
- Prompt Injection、越权访问、依赖漏洞、负载和灾备测试；
- 部署、迁移、回滚、事件响应和合规运营流程。

详见 [FINANCIAL_AGENT_IMPLEMENTATION.md](FINANCIAL_AGENT_IMPLEMENTATION.md)、[docs/production-readiness.md](docs/production-readiness.md) 和 [docs/release-status.md](docs/release-status.md)。

## 贡献

贡献流程和设计约束见 [CONTRIBUTING.md](CONTRIBUTING.md)。
