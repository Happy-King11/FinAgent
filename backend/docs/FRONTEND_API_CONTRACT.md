# FinAgent 前端接口契约

## 1. 基础约定

- API 前缀：`/api/v1`
- 健康检查：`GET /health/live`、`GET /health/ready`
- 认证：`Authorization: Bearer <JWT>`；开发模式可使用固定开发主体。
- 幂等：咨询创建、追加消息、确认和取消必须携带 `Idempotency-Key`。
- 通用响应：`{ request_id, trace_id, data, warnings, citations, compliance, error }`。
- 通用错误：前端只展示 `error.code` 和 `error.message`，不解析内部异常文本。

## 2. 咨询接口

### `POST /consultations`

请求：

```json
{
  "question": "请用 DCF 分析估值",
  "requested_intent": "valuation_analysis",
  "scene_input": {
    "scene": "valuation_analysis",
    "source_ids": ["user_supplied"],
    "currency": "CNY",
    "period": "FY2026",
    "dcf": {
      "free_cash_flows": [100, 110, 120],
      "wacc": 0.1,
      "terminal_growth": 0.03,
      "net_debt": 0,
      "shares_outstanding": 100
    }
  }
}
```

`requested_intent` 只能是八场景之一，并且必须与 `scene_input.scene` 一致。旧版 question-only 请求仍受支持。

响应 `data`：`case_id`、`status`、`answer`、`intent`、`result`、`risk_assessment`。

### 其他咨询操作

- `GET /consultations/{case_id}`：读取咨询状态。
- `POST /consultations/{case_id}/messages`：追加问题。
- `POST /consultations/{case_id}/confirm`：确认或拒绝高风险操作继续执行。
- `POST /consultations/{case_id}/cancel`：取消未完成咨询。

## 3. 八场景标识

- `single_stock_research`
- `product_explanation`
- `financial_knowledge`
- `portfolio_diagnosis`
- `valuation_analysis`
- `financial_statement_analysis`
- `risk_assessment`
- `compliance_consultation`

前端必须使用判别字段 `scene` 生成对应表单，不允许提交无约束任意 JSON。

## 4. 知识与产品

- `POST /documents`：上传当前版本支持的文本资料，字段为 `title`、`content`、`source`。
- `GET /documents/{document_id}`：读取文档与索引状态。
- `POST /knowledge/search`：字段为 `query`、`limit`。
- `GET /products`、`GET /products/{product_id}`：读取租户授权产品。

## 5. 画像、适当性与组合

- `GET /users/me/profile`：读取画像。
- `PUT /users/me/profile`：更新画像；已有画像必须携带 `If-Match: <version>`。
- `POST /suitability/check`：字段为 `product_risk_level`。
- `POST /portfolio/diagnoses`：字段为 `portfolio_id` 和可选 `risk_profile`。
- `GET /portfolio/diagnoses/{diagnosis_id}`：读取诊断。
- `POST /portfolio/diagnoses/{diagnosis_id}/review`：人工复核，要求 `review:write`。

## 6. 报告、任务和审计

- `POST /reports`、`GET /reports/{report_id}`。
- `GET /tasks/{task_id}`。
- `GET /audit/{case_id}`：要求 `audit:read`，响应包括 `events` 和 `chain_valid`。

## 7. 状态映射

- `received / classified / compliance_precheck / executing / compliance_postcheck`：处理中。
- `clarification_required`：需要补充问题。
- `waiting_confirmation`：显示确认/拒绝操作。
- `human_review`：显示人工审核中，不输出最终投资结论。
- `partial_success`：展示已验证部分和缺失字段。
- `completed`：正常完成。
- `blocked`：合规阻断。
- `failed / expired / cancelled`：终止状态。

## 8. 版本适配策略

前端仅依赖 `/api/v1` 已声明字段；未知字段忽略，缺少可选字段使用安全默认值。若后端返回未知 `status` 或 `intent`，前端以“未知状态/通用咨询”展示并保留原始值，不推断金融含义。

