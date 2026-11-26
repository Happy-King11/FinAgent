"""Quality-gate regression tests for source contracts and finance boundaries."""

from datetime import datetime, timedelta, timezone

from app.data.quality import DataQualityGate
from app.data.providers import QuoteRecord, SecurityMasterRecord


def test_data_quality_uses_source_contract_and_rejects_stale_data():
    master = [SecurityMasterRecord("CN1", "000001", "SZ", "Demo", "equity", "CNY", "listed", "A", "行业")]
    quote = [QuoteRecord("CN1", "2020-01-01", 1, 1, 1, 1, 1, 1, "CNY", "unadjusted")]
    report = DataQualityGate().validate(master, quote, source_id="dev_fixture", source_as_of=datetime.now(timezone.utc) - timedelta(days=4000))
    assert report.status == "failed"
    assert any(issue.code == "STALE_DATA" for issue in report.issues)


def test_data_quality_rejects_unknown_source_contract():
    master = []
    report = DataQualityGate().validate(master, [], source_id="missing-source", source_as_of=datetime.now(timezone.utc))
    assert report.status == "failed"
