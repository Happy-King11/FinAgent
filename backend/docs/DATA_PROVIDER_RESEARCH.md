# A 股与公募基金数据调研基线

本文件用于第二闭环开发阶段。当前数据只用于开发和测试，不代表生产授权。

## 1. 最小闭环

```text
脱敏持仓 -> 证券主数据 -> EOD 行情 -> 公司行动/复权 -> 行业分类
          -> 集中度与行业暴露 -> Data Quality Gate -> 风险提示/人工复核
```

## 2. 数据来源登记

| source_id | 数据 | 公开入口/候选 | 当前状态 | 生产使用条件 |
|---|---|---|---|---|
| `sse_public` | 上交所证券资料、交易日历、公告 | https://www.sse.com.cn/ | 待人工核验 | 确认抓取、保存、再分发和衍生结果边界 |
| `szse_public` | 深交所证券资料、交易日历、公告 | https://www.szse.cn/ | 待人工核验 | 同上 |
| `cninfo_public` | 上市公司公告、定期报告 | https://www.cninfo.com.cn/ | 待人工核验 | 同上；保留公告原文版本和哈希 |
| `fund_disclosure_public` | 基金法律文件、定期报告、净值披露 | https://www.csrc.gov.cn/ | 待人工核验 | 确认页面/文件许可和保存期限 |
| `dev_fixture` | 本仓库模拟证券、行情、基金和持仓 | `fixtures/data/` | 可用 | 仅 development/test，禁止生产路由 |
| `tushare_pro` | 证券、行情、财务、基金 API | https://tushare.pro/ | 后续评估 | 购买并确认 API、缓存、AI 和报告授权 |
| `wind` | 综合金融数据 | https://www.wind.com.cn/ | 后续评估 | 签署企业 License 和衍生数据条款 |
| `ifind` | 综合金融数据 | https://ft.10jqka.com.cn/ | 后续评估 | 同上 |
| `choice` | 综合金融数据 | https://choice.eastmoney.com/ | 后续评估 | 同上 |

公开页面不是自动生产授权。每一条数据进入生产前必须补齐合同/许可证明、获取时间、原始文件哈希和允许的使用范围。

## 3. 必需字段

### 证券主数据

`security_id`, `ticker`, `exchange`, `security_name`, `asset_class`, `currency`, `listing_status`, `effective_from`, `effective_to`, `source_as_of`。

### 行情

`security_id`, `trade_date`, `open`, `high`, `low`, `close`, `volume`, `amount`, `currency`, `adjustment`, `source_timestamp`, `source_id`。

### 公司行动

`security_id`, `event_type`, `ex_date`, `record_date`, `cash_dividend`, `split_ratio`, `rights_ratio`, `adjustment_factor`, `source_as_of`。

### 基金

`fund_id`, `fund_code`, `fund_name`, `fund_type`, `share_class`, `nav_date`, `nav`, `accumulated_nav`, `management_fee`, `custody_fee`, `subscription_rule`, `risk_level`, `document_version`, `source_as_of`。

### 持仓

持仓属于内部或用户授权数据，不应从公共数据源推断：`portfolio_id`, `security_id`, `quantity`, `cost_amount`, `market_value`, `currency`, `as_of`, `consent_ref`。

## 4. 验收门禁

- 所有必需字段存在且类型、币种、单位明确。
- 行情 `trade_date` 必须是有效交易日，且 `high >= max(open, close)`、`low <= min(open, close)`。
- 不允许以 0 或默认值填补缺失价格、净值或持仓数量。
- 结果必须携带 `source_id`、`source_as_of`、`schema_version` 和原始响应哈希。
- 超过 freshness policy 的数据返回 `stale_data`，不能伪装成实时数据。
- 主源和备用源冲突时返回 `data_source_conflict`，进入人工复核。
- `dev_fixture` 永远不能被生产配置选中。

## 5. 供应商评估顺序

先用 `dev_fixture` 完成 Provider Protocol、Data Quality Gate 和 portfolio diagnosis；再向 Tushare Pro、Wind、iFinD、Choice 索取同一字段样本和授权条款。比较维度：字段覆盖 25%、正确性 20%、授权 20%、时效/历史深度 15%、稳定性 10%、价格 10%。授权或关键字段不通过时直接淘汰。

