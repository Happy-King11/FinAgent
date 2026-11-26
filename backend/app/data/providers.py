"""数据供应商协议和开发夹具 Provider。"""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

from app.core.config import get_settings


@dataclass(frozen=True)
class SecurityMasterRecord:
    security_id: str
    ticker: str
    exchange: str
    security_name: str
    asset_class: str
    currency: str
    listing_status: str
    industry_code: str | None
    industry_name: str | None


@dataclass(frozen=True)
class QuoteRecord:
    security_id: str
    trade_date: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    amount: float
    currency: str
    adjustment: str


@dataclass(frozen=True)
class FundNavRecord:
    fund_id: str
    fund_code: str
    fund_name: str
    nav_date: str
    nav: float
    accumulated_nav: float
    currency: str = "CNY"


@dataclass(frozen=True)
class PortfolioPositionRecord:
    portfolio_id: str
    security_id: str
    quantity: float
    cost_amount: float
    market_value: float
    currency: str
    as_of: str
    consent_ref: str


class SecurityMasterProvider(Protocol):
    source_id: str

    def list_securities(self) -> list[SecurityMasterRecord]: ...


class MarketDataProvider(Protocol):
    source_id: str

    def list_quotes(self) -> list[QuoteRecord]: ...


class FundDataProvider(Protocol):
    source_id: str

    def list_fund_nav(self) -> list[FundNavRecord]: ...


class PortfolioDataProvider(Protocol):
    source_id: str

    def list_positions(self, portfolio_id: str) -> list[PortfolioPositionRecord]: ...


class FixtureDataProvider(SecurityMasterProvider, MarketDataProvider, FundDataProvider, PortfolioDataProvider):
    """仅用于开发验证；真实供应商实现相同 Protocol 即可替换。"""

    source_id = "dev_fixture"

    def __init__(self, data_dir: Path | None = None) -> None:
        if get_settings().app_env == "production":
            raise RuntimeError("dev_fixture is forbidden in production; configure an authorized data provider")
        self.data_dir = data_dir or Path(__file__).resolve().parents[2] / "fixtures" / "data"
        self._master = self._load("security_master.json")
        self._quotes = self._load("equity_eod.json")
        self._funds = self._load("fund_nav.json")
        self._positions = self._load("portfolio_positions.json")

    def _load(self, filename: str) -> dict:
        # source_id 校验防止误把其他供应商夹具接入当前计算链路。
        payload = json.loads((self.data_dir / filename).read_text(encoding="utf-8"))
        if payload.get("source_id") != self.source_id:
            raise ValueError(f"fixture {filename} has an unexpected source")
        return payload

    def list_securities(self) -> list[SecurityMasterRecord]:
        return [SecurityMasterRecord(**item) for item in self._master["items"]]

    def list_quotes(self) -> list[QuoteRecord]:
        return [QuoteRecord(**item) for item in self._quotes["items"]]

    def list_fund_nav(self) -> list[FundNavRecord]:
        return [FundNavRecord(**item) for item in self._funds["items"]]

    def list_positions(self, portfolio_id: str) -> list[PortfolioPositionRecord]:
        return [PortfolioPositionRecord(**item) for item in self._positions["items"] if item["portfolio_id"] == portfolio_id]

    def source_as_of(self) -> datetime:
        return datetime.fromisoformat(self._master["source_as_of"])
