"""金融引擎 golden cases 和缺失数据门禁。"""

from app.finance.comparables import ComparableCompanyEngine
from app.finance.dcf import DCFEngine
from app.finance.wacc import WACCEngine


def test_wacc_dcf_comps_golden_cases():
    wacc = WACCEngine().calculate(cost_of_equity=0.10, cost_of_debt=0.05, tax_rate=0.25, equity_value=75, debt_value=25)
    assert round(float(wacc.value or 0), 6) == 0.084375
    dcf = DCFEngine().calculate(free_cash_flows=[10, 11, 12], wacc=0.10, terminal_growth=0.02, shares_outstanding=10)
    assert dcf.status == "completed" and (dcf.value or 0) > 0
    comps = ComparableCompanyEngine().calculate(peer_multiples=[10, 12, 14], target_metric=5)
    assert comps.value == 60


def test_finance_engine_does_not_fill_missing_inputs():
    result = DCFEngine().calculate(free_cash_flows=[], wacc=0.1, terminal_growth=0.02, shares_outstanding=None)
    assert result.status == "insufficient_data"
    assert "free_cash_flows" in result.missing_fields
