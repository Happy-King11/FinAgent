"""Data-source contract loading and authorization checks."""

from pathlib import Path

import yaml


class DataSourceContract:
    def __init__(self, payload: dict):
        self.payload = payload
        self.source_id = str(payload["source_id"])
        self.authorization_scope = str(payload.get("authorization_scope", ""))
        self.max_age_days = int(payload.get("freshness", {}).get("max_age_days", 0))

    @property
    def authorized(self) -> bool:
        return self.authorization_scope not in {"", "synthetic_data_only"} or self.payload.get("environment") == "development_only"


def load_data_source_contract(source_id: str, directory: Path | None = None) -> DataSourceContract:
    root = directory or Path(__file__).resolve().parents[2] / "configs" / "data_sources"
    for path in root.glob("*.yaml"):
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if payload.get("source_id") == source_id:
            return DataSourceContract(payload)
    raise ValueError(f"data source contract not found: {source_id}")
