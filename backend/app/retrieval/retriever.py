"""开发期内存检索器：先做租户硬过滤，再按词项命中排序。"""

from dataclasses import dataclass
from typing import Any
from datetime import datetime, timezone


@dataclass(frozen=True)
class Citation:
    document_id: str
    object_version: str
    title: str
    source: str
    section_path: str | None = None
    page: int | None = None
    sha256: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {"document_id": self.document_id, "object_version": self.object_version, "title": self.title, "source": self.source, "section_path": self.section_path, "page": self.page, "sha256": self.sha256}


class InMemoryRetriever:
    def __init__(self) -> None:
        self._documents: list[tuple[Any, Citation]] = []

    def add(self, document: Any) -> None:
        citation = Citation(document.id, document.object_version, document.title, document.source, sha256=document.sha256)
        self._documents.append((document, citation))

    def replace_tenant(self, tenant_id: str, documents: list[Any]) -> None:
        """Replace one tenant's rebuildable index from the authoritative source."""
        self._documents = [
            (document, citation)
            for document, citation in self._documents
            if document.tenant_id != tenant_id
        ]
        for document in documents:
            if document.tenant_id == tenant_id and document.status == "ready":
                self.add(document)

    def search(self, tenant_id: str, query: str, limit: int = 5) -> list[tuple[str, Citation]]:
        # 租户过滤必须先于召回，不能交给相似度模型决定数据边界。
        terms = {term.lower() for term in query.split() if len(term) > 1}
        ranked = []
        for document, citation in self._documents:
            if document.tenant_id != tenant_id:
                continue
            if document.status != "ready":
                continue
            if document.authorization_expires_at and document.authorization_expires_at <= datetime.now(timezone.utc):
                continue
            haystack = f"{document.title} {document.content}".lower()
            score = sum(term in haystack for term in terms)
            if score:
                ranked.append((score, document, citation))
        ranked.sort(key=lambda item: item[0], reverse=True)
        return [(document.content, citation) for _, document, citation in ranked[:limit]]
