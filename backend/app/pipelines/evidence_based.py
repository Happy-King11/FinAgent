"""Evidence-only pipelines for scenes that do not yet have structured calculation input."""

from dataclasses import dataclass

from app.pipelines.types import PipelineOutput


@dataclass(frozen=True)
class EvidenceBasedPipeline:
    scene_id: str
    scope_notice: str
    required_structured_inputs: tuple[str, ...] = ()

    def run(self, question: str, retrieved: list[tuple[str, object]]) -> PipelineOutput:
        del question  # Routing owns intent; this pipeline consumes only authorized evidence.
        if not retrieved:
            return PipelineOutput(
                facts="目前没有足够的授权资料支持该问题。",
                warnings=(self.scope_notice,),
                missing_fields=("authorized_evidence",) + self.required_structured_inputs,
                result={"scene_id": self.scene_id, "calculation_performed": False},
            )
        snippets = [content[:800] for content, _ in retrieved]
        citations = tuple(citation.as_dict() for _, citation in retrieved)
        warnings = (self.scope_notice,) if self.required_structured_inputs else ()
        return PipelineOutput(
            facts="\n\n".join(snippets),
            citations=citations,
            warnings=warnings,
            missing_fields=self.required_structured_inputs,
            result={"scene_id": self.scene_id, "calculation_performed": False},
        )
