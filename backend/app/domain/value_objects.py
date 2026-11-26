"""不可变领域值对象，例如可定位的证据引用。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class EvidenceRef:
    document_id: str
    object_version: str
    page: int | None = None
    section_path: str | None = None
    sha256: str | None = None
