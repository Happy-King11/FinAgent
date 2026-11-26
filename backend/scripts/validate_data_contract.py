"""Validate the development data fixtures used by the second delivery loop."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "fixtures" / "data"


def load(name: str) -> dict:
    # 所有夹具必须声明同一开发 source 和 schema 版本。
    path = DATA / name
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["source_id"] == "dev_fixture", f"{name}: unexpected source"
    assert payload["schema_version"] == "1.0.0", f"{name}: missing schema version"
    assert payload["items"], f"{name}: empty fixture"
    return payload


def validate() -> None:
    # 校验主数据映射、行情边界、基金费用和持仓授权引用。
    master = load("security_master.json")
    ids = {item["security_id"] for item in master["items"]}
    quotes = load("equity_eod.json")["items"]
    for quote in quotes:
        assert quote["security_id"] in ids
        assert quote["currency"] == "CNY"
        assert quote["high"] >= max(quote["open"], quote["close"])
        assert quote["low"] <= min(quote["open"], quote["close"])
        assert quote["volume"] >= 0 and quote["amount"] >= 0

    funds = load("fund_nav.json")["items"]
    for fund in funds:
        assert fund["nav"] > 0 and fund["accumulated_nav"] > 0
        assert 0 <= fund["management_fee"] <= 1
        assert 0 <= fund["custody_fee"] <= 1

    positions = load("portfolio_positions.json")["items"]
    assert all(position["consent_ref"] for position in positions)
    assert all(position["market_value"] >= 0 for position in positions)
    assert {position["security_id"] for position in positions} <= ids


if __name__ == "__main__":
    validate()
    print("data contract valid: dev_fixture")
