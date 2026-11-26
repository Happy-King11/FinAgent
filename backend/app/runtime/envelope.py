"""Provider result envelopes that preserve provenance at application boundaries."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Generic, Mapping, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class DataEnvelope(Generic[T]):
    data: T
    source_id: str
    source_version: str = ""
    retrieved_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source_as_of: str = ""
    authorization_scope: str = ""
    freshness_status: str = "unknown"
    quality_issues: tuple[str, ...] = ()
    request_id: str = ""
    schema_version: str = "1.0.0"
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.source_id:
            raise ValueError("source_id is required")
        object.__setattr__(self, "quality_issues", tuple(self.quality_issues))
        object.__setattr__(self, "metadata", dict(self.metadata))

    @property
    def items(self) -> T:
        """Compatibility alias for list-returning Provider consumers."""
        return self.data

    def as_dict(self) -> dict:
        return {
            "source_id": self.source_id,
            "source_version": self.source_version,
            "retrieved_at": self.retrieved_at.isoformat(),
            "source_as_of": self.source_as_of,
            "authorization_scope": self.authorization_scope,
            "freshness_status": self.freshness_status,
            "quality_issues": list(self.quality_issues),
            "request_id": self.request_id,
            "schema_version": self.schema_version,
            "metadata": dict(self.metadata),
        }


def envelope_provider_result(provider: object, data: T, *, request_id: str = "") -> DataEnvelope[T]:
    """Wrap an unchanged Provider result without changing its Protocol."""
    source_as_of = getattr(provider, "source_as_of", "")
    if callable(source_as_of):
        source_as_of = source_as_of()
    return DataEnvelope(
        data=data,
        source_id=str(getattr(provider, "source_id", "")),
        source_as_of=str(source_as_of or ""),
        request_id=request_id,
    )
