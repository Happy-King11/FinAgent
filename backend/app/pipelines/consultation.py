"""Backward-compatible financial-knowledge pipeline alias."""

from app.pipelines.evidence_based import EvidenceBasedPipeline


class ConsultationPipeline(EvidenceBasedPipeline):
    def __init__(self) -> None:
        super().__init__(
            scene_id="financial_knowledge",
            scope_notice="仅基于授权知识资料解释，不把模型常识作为金融事实。",
        )
