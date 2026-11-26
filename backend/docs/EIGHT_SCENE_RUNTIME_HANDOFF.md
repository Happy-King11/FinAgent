# FinAgent 八场景运行时源码交接说明

> 文档用途：交接给后续负责源码实现的工作区聊天，使其无需重新讨论业务范围即可继续开发。
>
> 当前阶段：内部测试 PoC；八场景运行时第一批已落地。
>
> 更新时间：2026-11-09。

## 1. 必须继承的项目原则

本项目是 FastAPI 金融咨询 Agent，不是自动交易系统。后续开发必须遵守仓库根目录 `AGENTS.md` 和以下不可变边界：

1. 金融数字由确定性代码生成，LLM 不得计算、修改或覆盖 Finance Engine 输出。
2. 不实现下单、转账、删除或其他不可逆金融操作。
3. 所有 Agent 工具调用必须经过项目自有的 `ToolRegistry` 和 `ToolGateway`。
4. 当前阶段不引入 LangChain Tools、AgentExecutor 或 LangGraph。
5. Risk Agent 负责发现和解释风险，不能覆盖确定性 Risk Policy、Compliance Engine、Data Quality Gate 或 Finance Engine。
6. 当前仅允许使用 `dev_fixture`、用户明确输入和授权上传文档。
7. 模型常识不能作为行情、财务报表、产品事实或用户画像的权威来源。
8. PostgreSQL/授权 Provider/对象存储是未来权威源；向量库只是可重建索引。
9. 所有外部或注册工具不得绕过 `ToolGateway`。
10. 生产环境必须继续 fail-closed，不得削弱 `Settings.validate_production_safety()` 或 `Container` 的生产阻断。

## 2. 已冻结的八个应用场景

系统对外只保留以下八个版本化 Intent：

1. `single_stock_research`：单股研究。
2. `product_explanation`：产品解释。
3. `financial_knowledge`：金融知识解释。
4. `portfolio_diagnosis`：组合诊断。
5. `valuation_analysis`：估值分析。
6. `financial_statement_analysis`：财报分析。
7. `risk_assessment`：风险评估。
8. `compliance_consultation`：合规咨询。

业务边界已经确认：

- 单股研究不输出直接买入、卖出、增持、减持指令。
- LLM 不生成目标价、止损价、收益率或仓位比例。
- 目标价值只能由确定性估值引擎根据结构化输入生成。
- 合规咨询只解释版本化规则和授权制度，不构成法律意见。
- 产品解释只能引用租户下的授权产品记录。
- 金融知识解释优先使用授权文档；无授权证据时必须披露资料不足。

未知意图不再路由到旧的 `consultation` Intent，而是路由到 `financial_knowledge` 并进入 `clarification_required`。

## 3. 风险评估对象

风险评估采用统一入口，但风险对象必须是以下五类之一：

```text
user
product
security
portfolio
consultation
```

对应源码为：

- `app/risk/policy.py`
- `app/agents/risk.py`

### 3.1 Risk Policy 与 Risk Agent 的职责

```text
结构化事实、数据质量、缺失字段、合规结果
                    |
                    v
           RiskPolicyEngine
       确定风险等级和处置动作
                    |
                    v
              RiskAgent
        解释原因、生成结构化摘要
```

`RiskPolicyEngine` 是决策权威，当前版本为 `risk_policy_v1.0.0`。它输出：

- `risk_level`: `low | medium | high`
- `disposition`: `allow | disclose | human_review | block`
- `reason_codes`
- `policy_version`

当前确定性规则：

- 合规阻断：`high + block`。
- 合规要求审批：`high + human_review`。
- 数据质量失败：`high + human_review`。
- 缺少授权证据：`medium + disclose`。
- 缺少必需结构化输入：`medium + disclose`。
- 存在其他风险提示：`medium + disclose`。
- 无上述问题：`low + allow`。

Risk Agent 输出始终包含：

```json
{
  "decision_source": "deterministic_policy",
  "can_override_policy": false
}
```

禁止后续把 `can_override_policy` 改成 `true`，也禁止允许模型生成的字段覆盖 Policy 结果。

## 4. 当前运行链路

```text
FastAPI API
   |
   v
ConsultationService
   |
   +--> IntentRouter：八场景确定性分类
   |
   +--> ComplianceEngine：输入预审
   |
   +--> PipelineRegistry：解析版本化 Pipeline
   |
   +--> ToolExecutionContext：注入 Pipeline 工具白名单/黑名单
   |
   +--> ToolGateway：租户、授权、Schema、超时、重试、熔断、缓存、确认、审批
   |
   +--> Pipeline：生成 PipelineOutput
   |
   +--> Advisor：仅基于授权事实整理自然语言
   |
   +--> ComplianceEngine：输出后审
   |
   +--> RiskPolicyEngine -> RiskAgent
   |
   +--> ConsultationCase 持久化 + Audit
```

主要实现位置：

- `app/agents/intents.py`
- `app/agents/router.py`
- `app/application/consultation_service.py`
- `app/application/container.py`
- `app/pipelines/registry.py`
- `app/pipelines/evidence_based.py`
- `app/pipelines/types.py`
- `app/tools/gateway.py`
- `app/tools/financial.py`

## 5. Pipeline 契约

八个场景均已在 `Container` 注册 `PipelineManifest`，版本为 `1.0.0`。Manifest 至少声明：

- `pipeline_id`
- `version`
- `supported_intents`
- `required_inputs`
- `allowed_tools`
- `blocked_tools`
- `risk_level`
- `output_schema`
- `timeout_seconds`
- `audit_required`

Pipeline 统一返回 `app/pipelines/types.py` 中的 `PipelineOutput`：

```python
@dataclass(frozen=True)
class PipelineOutput:
    facts: str
    citations: tuple[dict[str, Any], ...] = ()
    warnings: tuple[str, ...] = ()
    missing_fields: tuple[str, ...] = ()
    result: dict[str, Any] = field(default_factory=dict)
```

### 5.1 当前完成度

已形成完整事实回答链路：

- `product_explanation`
- `financial_knowledge`

已完成 Intent、Manifest、风险和安全降级，但尚缺结构化业务输入：

- `single_stock_research`
- `portfolio_diagnosis` 的统一咨询入口
- `valuation_analysis`
- `financial_statement_analysis`
- `risk_assessment`
- `compliance_consultation` 的正式规则知识库

这些场景目前使用 `EvidenceBasedPipeline`：

- 有授权资料时整理授权事实；
- 缺少结构化输入时设置 `missing_fields`；
- 不执行未经授权的计算；
- 不让 LLM 补充数字；
- 在 `risk_assessment` 中形成 `medium + disclose`。

这是一项有意的 fail-closed 行为，不得用 Prompt 猜测数据来“提高完成率”。

## 6. ToolGateway 治理

`ToolExecutionContext` 已增加：

```python
allowed_tools: frozenset[str] | None
blocked_tools: frozenset[str]
```

Pipeline 执行时，`ConsultationService` 会把 Manifest 的工具白名单和黑名单写入 Context。`ToolGateway` 在调用工具前强制检查：

```text
TOOL_NOT_ALLOWED
```

`allowed_tools=None` 只用于兼容非 Pipeline 的内部调用。Agent/Pipeline 执行必须显式传入白名单。

ToolGateway 现有治理不能被删除：

- 租户范围检查；
- 数据授权检查；
- 确认和审批；
- 输入输出 Schema；
- 超时；
- 幂等工具重试；
- 熔断；
- fallback；
- 缓存；
- 合规检查。

### 6.1 已注册的确定性金融工具

`app/tools/financial.py` 已通过 ToolGateway 注册：

- `dcf_calculate`
- `wacc_calculate`
- `comparable_valuation`
- `scenario_calculate`

这些工具：

- 风险级别为 `L1`；
- `side_effect=read_only`；
- 使用 JSON Schema 子集校验输入输出；
- 返回 `FinanceResult.as_dict()`；
- 保留 `formula_version`、假设、数据来源、缺失字段和 warning；
- 不调用 LLM。

估值 Pipeline 的 Manifest 已允许上述工具，但当前自然语言咨询尚未携带强类型估值输入，因此不会自动执行估值。

## 7. ConsultationCase 和 API 输出变化

`ConsultationCase` 已新增：

```python
result: dict[str, Any]
risk_assessment: dict[str, Any] | None
```

API 咨询响应的 `data` 当前包含：

```json
{
  "case_id": "case_...",
  "status": "completed",
  "answer": "...",
  "intent": "product_explanation",
  "result": {},
  "risk_assessment": {}
}
```

数据库同步变更：

- SQLAlchemy：`app/infrastructure/database/models.py`
- SQL Repository：`app/repositories/sql.py`
- 新迁移：`migrations/010_consultation_results.sql`

不得编辑已经发布的旧迁移。后续数据库变化必须新增编号迁移。

## 8. 数据范围

当前内测只允许三类来源：

```text
dev_fixture
user_supplied
authorized_document
```

其中：

- `dev_fixture` 仅用于开发和自动测试；
- `user_supplied` 必须记录为用户明确提供的假设或输入；
- `authorized_document` 必须保留来源、授权范围、版本、哈希和有效期；
- 模型输出不得注册成数据源；
- 未配置 `DataSourceContract` 的 Provider 不得进入计算链路；
- 缺失值不得默认填零；
- 实时价格、正式收盘价和财报期间值不得混用。

## 9. 下一批源码任务

后续源码聊天应按以下顺序实施，不要同时摊开所有模块。

### 9.1 第一优先级：八场景强类型请求契约

为咨询入口增加可选但强类型的场景输入。不要使用无约束的 `dict[str, Any]` 作为最终方案。

建议设计：

```text
ConsultationCreate
  question
  requested_intent?
  scene_input?
```

`scene_input` 使用 Pydantic 判别联合：

- `SingleStockResearchInput`
- `ProductExplanationInput`
- `FinancialKnowledgeInput`
- `PortfolioDiagnosisInput`
- `ValuationAnalysisInput`
- `FinancialStatementAnalysisInput`
- `RiskAssessmentInput`
- `ComplianceConsultationInput`

必须校验 `requested_intent` 与 `scene_input` 类型一致。用户显式指定 Intent 时仍要经过合规和权限检查，不能绕过 Router 风险标记。

### 9.2 第二优先级：估值 Pipeline

将结构化估值输入映射到以下 ToolGateway 工具：

```text
wacc_calculate
dcf_calculate
comparable_valuation
scenario_calculate
```

执行要求：

1. 先过 Data Quality Gate。
2. 每个数字记录 `source_id` 或标为 `user_supplied`。
3. ToolGateway 调用必须携带 Pipeline allowlist。
4. Pipeline 只消费工具结构化结果。
5. Advisor 只能解释工具结果。
6. LLM 生成的目标价一律拒绝进入 `result`。

### 9.3 第三优先级：财报分析

增加合成财务报表 fixture 和字段契约，至少覆盖：

- 利润表；
- 资产负债表；
- 现金流量表；
- 报告期；
- 币种；
- 单位；
- 合并/母公司口径；
- 审计状态；
- 公告时间；
- 数据来源。

同比、环比、利润率、偿债和现金流指标必须由确定性代码计算。

### 9.4 第四优先级：单股研究

单股研究只允许整合：

- 授权公司资料；
- 结构化财报结果；
- Finance Engine 估值结果；
- 明确来源的行情；
- Risk Agent 结构化风险结论。

输出建议结构：

```text
company_facts
financial_statement_findings
valuation_results
risk_assessment
bull_evidence
bear_evidence
missing_data
citations
```

不得增加 `BUY/SELL`、目标收益率、止损价或仓位比例字段。

### 9.5 第五优先级：统一组合诊断

仓库已有独立组合诊断：

- `app/portfolio/diagnosis.py`
- `app/application/portfolio_service.py`

需要将其接入统一 `portfolio_diagnosis` Pipeline，但不要复制计算逻辑。统一入口应复用现有确定性实现，并继续要求：

- `portfolio_ref`；
- 用户授权或 consent；
- 已确认风险画像；
- Data Quality Gate；
- 缺数据时 `insufficient_data`；
- 集中度阈值触发人工复核。

### 9.6 第六优先级：工具调用审计

扩展 `ToolExecutionContext`：

```text
case_id
trace_id
pipeline_id
pipeline_version
```

每次 ToolGateway 调用至少记录：

- 工具 ID 和版本；
- 输入 Schema 版本；
- 脱敏输入摘要或哈希；
- 输出摘要或哈希；
- 开始和结束时间；
- cache/fallback/retry 情况；
- 成功或稳定错误码；
- tenant/case/trace/pipeline；
- 风险、确认和审批结果。

不得把密钥、完整 Prompt、用户敏感字段或未经脱敏的持仓明细写入普通日志。

## 10. 下一批验收标准

后续改造至少满足：

1. IntentRegistry 仍然只有八个正式场景。
2. 每个场景都有独立、版本化、可校验的输入和输出 Schema。
3. Pipeline 不能调用不在 Manifest allowlist 中的工具。
4. 任一缺少授权来源的金融数字都会被拒绝或标记 `insufficient_data`。
5. Risk Agent 输出不能改变 Policy 决策。
6. 合规阻断优先于 Agent 和 Pipeline 结论。
7. 估值结果保留公式版本、假设、币种、单位、期间和来源。
8. SQL 模型与新编号迁移同步。
9. 每项行为变化都增加单元测试。
10. 保持租户隔离、审计链和生产 fail-closed。

## 11. 当前测试状态

已执行：

```bash
python -m compileall -q app tests
python -m pytest tests/test_eight_scene_runtime.py -q
python -m pytest tests --ignore=tests/test_first_loop.py --ignore=tests/test_second_loop.py -k "not test_supervisor_executor_blocks_on_critical_failure" -q
docker compose --env-file backend/.env config --quiet
```

结果：

- 八场景新增测试：`13 passed`。
- 离线非 TestClient 回归：`59 passed, 1 deselected`。
- 编译通过。
- Compose 配置校验通过。

当前机器只有 Python 3.14。Starlette TestClient 在 Windows/AnyIO 创建 asyncio 自管道时卡在 `socketpair`，因此两个使用 TestClient 的既有测试文件没有在当前环境完成。另有一个旧测试会访问 `https://llm.invalid` 等待网络超时。后续应在 Python 3.11 或 3.12 环境运行完整套件，不应删除 API 测试来掩盖环境问题。

## 12. 已修改或新增的主要文件

```text
app/agents/intents.py
app/agents/router.py
app/agents/risk.py
app/api/v1/router.py
app/application/consultation_service.py
app/application/container.py
app/domain/entities.py
app/infrastructure/database/models.py
app/pipelines/consultation.py
app/pipelines/evidence_based.py
app/pipelines/product_explanation.py
app/pipelines/types.py
app/repositories/sql.py
app/risk/__init__.py
app/risk/policy.py
app/tools/financial.py
app/tools/gateway.py
docs/release-status.md
migrations/010_consultation_results.sql
tests/test_eight_scene_runtime.py
tests/test_phase6_contracts.py
```

工作区中的未跟踪 `AGENTS.md`、`CLAUDE.md` 属于用户已有文件，本阶段没有修改或删除。

## 13. 给后续源码聊天的直接执行指令

可以将下面内容直接作为下一聊天的任务说明：

```text
请先完整阅读仓库 AGENTS.md、FINANCIAL_AGENT_IMPLEMENTATION.md 和
docs/EIGHT_SCENE_RUNTIME_HANDOFF.md。

继续 FinAgent 八场景内部测试阶段。不要引入 LangChain；保持 ToolRegistry、
ToolGateway、确定性 Finance Engine、Compliance Engine 和 RiskPolicyEngine 的边界。

本轮优先实现八场景强类型 scene_input 判别联合，并先完成 valuation_analysis：
1. 定义 Pydantic 输入/输出 Schema；
2. 验证 requested_intent 与 scene_input 一致；
3. 通过 ToolGateway 调用 WACC/DCF/可比估值/情景工具；
4. 所有输入记录 user_supplied 或授权 source_id；
5. LLM 只能解释 FinanceResult，不能生成或覆盖数字；
6. 将结果、风险、引用和缺失字段写入 ConsultationCase；
7. 增加 Router、Schema、Tool allowlist、缺失数据、合规、风险和租户隔离测试；
8. 保持现有 API 向后兼容，旧 question-only 请求继续安全降级。

先检查工作区未提交改动，不覆盖无关用户文件。实现后运行 compileall、相关单测、
非网络回归和 `docker compose --env-file backend/.env config`，并报告当前环境无法执行的测试。
```

