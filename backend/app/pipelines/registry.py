"""Versioned Pipeline manifests and registry."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class PipelineManifest:
    pipeline_id: str
    version: str
    supported_intents: tuple[str, ...] = ()
    required_inputs: tuple[str, ...] = ()
    required_skills: tuple[str, ...] = ()
    allowed_tools: tuple[str, ...] = ()
    blocked_tools: tuple[str, ...] = ()
    risk_level: str = "low"
    output_schema: str = ""
    timeout_seconds: int = 60
    audit_required: bool = True

    def validate(self) -> None:
        if not self.pipeline_id or not self.version or not self.output_schema:
            raise ValueError("pipeline manifest requires id, version and output_schema")
        if self.timeout_seconds <= 0:
            raise ValueError("pipeline timeout must be positive")
        if self.risk_level not in {"low", "medium", "high"}:
            raise ValueError("invalid pipeline risk level")
        if set(self.allowed_tools) & set(self.blocked_tools):
            raise ValueError("a tool cannot be both allowed and blocked")


class PipelineRegistry:
    def __init__(self) -> None:
        self._pipelines: dict[str, tuple[PipelineManifest, Any]] = {}

    def register(self, manifest: PipelineManifest, pipeline: Any) -> None:
        manifest.validate()
        key = f"{manifest.pipeline_id}@{manifest.version}"
        if key in self._pipelines:
            raise ValueError(f"pipeline already registered: {key}")
        self._pipelines[key] = (manifest, pipeline)

    def get(self, pipeline_ref: str) -> Any:
        try:
            return self._pipelines[pipeline_ref][1]
        except KeyError as exc:
            raise KeyError(f"pipeline is not registered: {pipeline_ref}") from exc

    def manifest(self, pipeline_ref: str) -> PipelineManifest:
        try:
            return self._pipelines[pipeline_ref][0]
        except KeyError as exc:
            raise KeyError(f"pipeline is not registered: {pipeline_ref}") from exc

    def resolve(self, pipeline_refs: tuple[str, ...], *, intent: str, available_inputs: set[str], available_skills: set[str] | None = None) -> tuple[PipelineManifest, Any]:
        """Return the first registered pipeline whose declared requirements are met."""
        skills = available_skills or set()
        for pipeline_ref in pipeline_refs:
            try:
                manifest = self.manifest(pipeline_ref)
                pipeline = self.get(pipeline_ref)
            except KeyError:
                continue
            if intent not in manifest.supported_intents:
                continue
            if not set(manifest.required_inputs).issubset(available_inputs):
                continue
            if not set(manifest.required_skills).issubset(skills):
                continue
            return manifest, pipeline
        raise ValueError("no eligible pipeline is registered for the routed intent")
