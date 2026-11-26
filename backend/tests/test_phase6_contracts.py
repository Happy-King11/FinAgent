"""Phase 6 contracts: versioned routing, manifests, tools and deterministic plans."""

from dataclasses import replace

import pytest

from app.agents.intents import IntentRegistry
from app.agents.router import IntentRouter
from app.agents.supervisor import AgentRegistry, PlanExecutionResult, SupervisorExecutor, SupervisorPlan
from app.core.constants import RiskLevel
from app.core.exceptions import DomainError
from app.llm.openai_compatible import OpenAICompatibleClient
from app.pipelines.registry import PipelineManifest, PipelineRegistry
from app.tools.gateway import ToolExecutionContext, ToolGateway
from app.tools.registry import ToolManifest


def _node(step_id: str, *, refs: tuple[str, ...] = ()) -> dict:
    return {"step_id": step_id, "agent": "researcher", "output_schema": "ResearchResult", "input_refs": refs}


def _plan(nodes: tuple[dict, ...], *, edges: tuple[tuple[str, str], ...] = ()) -> SupervisorPlan:
    return SupervisorPlan("plan-1", "case-1", "trace-1", "1.0.0", nodes, edges=edges)


def test_intent_registry_and_router_return_versioned_route_contract():
    registry = IntentRegistry()
    definition = registry.get("product_explanation")
    assert definition.version == "1.0.0"
    assert definition.pipeline_ref == "product_explanation@1.0.0"

    result = IntentRouter(registry).route("Please explain product fees and risk", "trace-1")
    assert result.primary_intent == "product_explanation"
    assert result.risk_level == RiskLevel.LOW
    assert result.candidate_pipelines == ("product_explanation@1.0.0",)
    assert result.as_dict()["router_version"] == "rules_v1.0.0"


def test_unknown_intent_requires_clarification_and_uses_financial_knowledge_pipeline():
    result = IntentRouter().route("What should I do next?", "trace-1")
    assert result.primary_intent == "financial_knowledge"
    assert result.requires_clarification is True
    assert result.candidate_pipelines == ("financial_knowledge@1.0.0",)


@pytest.mark.parametrize(
    "manifest",
    [
        PipelineManifest("", "1.0.0", output_schema="Result"),
        PipelineManifest("pipeline", "", output_schema="Result"),
        PipelineManifest("pipeline", "1.0.0", output_schema=""),
        PipelineManifest("pipeline", "1.0.0", output_schema="Result", timeout_seconds=0),
        PipelineManifest("pipeline", "1.0.0", output_schema="Result", risk_level="critical"),
        PipelineManifest("pipeline", "1.0.0", output_schema="Result", allowed_tools=("a",), blocked_tools=("a",)),
    ],
)
def test_pipeline_manifest_rejects_invalid_contracts(manifest):
    with pytest.raises(ValueError):
        manifest.validate()


def test_pipeline_registry_resolves_only_eligible_registered_pipeline():
    registry = PipelineRegistry()
    pipeline = object()
    manifest = PipelineManifest("knowledge", "1.0.0", ("knowledge_summary",), ("question",), output_schema="Answer")
    registry.register(manifest, pipeline)

    selected, resolved = registry.resolve(("knowledge@1.0.0",), intent="knowledge_summary", available_inputs={"question"})
    assert selected == manifest
    assert resolved is pipeline
    with pytest.raises(ValueError):
        registry.resolve(("knowledge@1.0.0",), intent="knowledge_summary", available_inputs=set())


@pytest.mark.parametrize(
    "manifest",
    [
        ToolManifest("tool", risk_level="invalid"),
        ToolManifest("tool", side_effect="unknown"),
        ToolManifest("tool", timeout_seconds=0),
        ToolManifest("tool", cache_ttl_seconds=0),
        ToolManifest("tool", risk_level="L3"),
    ],
)
def test_tool_manifest_rejects_invalid_risk_and_execution_options(manifest):
    with pytest.raises(ValueError):
        manifest.validate()


def test_tool_gateway_enforces_confirmation_entitlement_contract_cache_and_fallback():
    calls = {"primary": 0, "cached": 0}
    gateway = ToolGateway()
    gateway.register("fallback", lambda tenant_id, query: {"source": "fallback"}, ToolManifest("fallback", input_schema={"type": "object", "required": ["tenant_id", "query"]}, output_schema={"type": "object"}))

    def failing_tool(tenant_id: str, query: str):
        calls["primary"] += 1
        raise RuntimeError("provider unavailable")

    gateway.register("primary", failing_tool, ToolManifest("primary", fallback_tool_id="fallback", input_schema={"type": "object", "required": ["tenant_id", "query"]}, output_schema={"type": "object"}))
    context = ToolExecutionContext("tenant-a", confirmed=True, data_entitlements=frozenset({"market-data"}))
    assert gateway.execute("primary", context=context, tenant_id="tenant-a", query="fund") == {"source": "fallback"}

    def cached_tool(tenant_id: str, query: str):
        calls["cached"] += 1
        return {"query": query}

    gateway.register("cached", cached_tool, ToolManifest("cached", requires_confirmation=True, required_data_entitlement="market-data", input_schema={"type": "object", "required": ["tenant_id", "query"], "properties": {"tenant_id": {"type": "string"}, "query": {"type": "string"}}}, output_schema={"type": "object", "required": ["query"]}, cache_ttl_seconds=60))
    assert gateway.execute("cached", context=context, tenant_id="tenant-a", query="fund") == {"query": "fund"}
    assert gateway.execute("cached", context=context, tenant_id="tenant-a", query="fund") == {"query": "fund"}
    assert calls["cached"] == 1

    with pytest.raises(DomainError, match="confirmation"):
        gateway.execute("cached", context=ToolExecutionContext("tenant-a", data_entitlements=frozenset({"market-data"})), tenant_id="tenant-a", query="fund")
    with pytest.raises(DomainError, match="entitlement"):
        gateway.execute("cached", context=ToolExecutionContext("tenant-a", confirmed=True), tenant_id="tenant-a", query="fund")
    with pytest.raises(DomainError, match="tenant"):
        gateway.execute("cached", context=context, tenant_id="tenant-b", query="fund")
    with pytest.raises(DomainError, match="missing"):
        gateway.execute("cached", context=context, tenant_id="tenant-a")
    with pytest.raises(DomainError, match="not allowed"):
        gateway.execute(
            "cached",
            context=ToolExecutionContext("tenant-a", confirmed=True, data_entitlements=frozenset({"market-data"}), allowed_tools=frozenset({"fallback"})),
            tenant_id="tenant-a",
            query="fund",
        )


def test_supervisor_plan_rejects_duplicate_dangling_cyclic_and_oversized_graphs():
    with pytest.raises(ValueError, match="unique"):
        _plan((_node("one"), _node("one"))).validate()
    with pytest.raises(ValueError, match="input_refs"):
        _plan((_node("one", refs=("missing",)),)).validate()
    with pytest.raises(ValueError, match="acyclic"):
        _plan((_node("one"), _node("two")), edges=(("one", "two"), ("two", "one"))).validate()
    with pytest.raises(ValueError, match="one to five"):
        _plan(tuple(_node(str(index)) for index in range(6))).validate()


def test_supervisor_plan_accepts_deterministic_acyclic_data_flow():
    plan = _plan((_node("retrieve"), _node("advise", refs=("retrieve",))), edges=(("retrieve", "advise"), ("advise", "advisor")))
    plan.validate()


def test_supervisor_plan_executes_only_declared_inputs_and_propagates_failures():
    agents = AgentRegistry()
    agents.register("source", lambda inputs: {"value": 3})
    agents.register("optional", lambda inputs: (_ for _ in ()).throw(RuntimeError("optional failed")))
    agents.register("final", lambda inputs: {"total": inputs["source"]["value"]})
    executor = SupervisorExecutor(agents)
    plan = SupervisorPlan(
        "plan-1", "case-1", "trace-1", "1.0.0",
        (
            {"step_id": "source", "agent": "source", "output_schema": "Source"},
            {"step_id": "optional", "agent": "optional", "output_schema": "Optional", "critical": False},
            {"step_id": "final", "agent": "final", "output_schema": "Final", "input_refs": ("source",)},
        ),
    )
    result = executor.execute(plan, initial_input={"question": "calculate"})
    assert result.status == "partial_success"
    assert result.outputs["final"] == {"total": 3}
    assert "optional" in result.failed_steps


def test_supervisor_executor_blocks_on_critical_failure():
    agents = AgentRegistry()
    agents.register("broken", lambda inputs: (_ for _ in ()).throw(RuntimeError("failed")))
    plan = _plan(({"step_id": "broken", "agent": "broken", "output_schema": "Result"},))
    result = SupervisorExecutor(agents).execute(plan)
    assert result.status == "blocked"
    assert "broken" in result.failed_steps


    client = OpenAICompatibleClient("https://llm.invalid", "runtime-only", "test-model")
    with pytest.raises(RuntimeError, match="transport"):
        client.complete("summarize this")
