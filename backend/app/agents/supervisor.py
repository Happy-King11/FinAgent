"""Deterministic DAG plan validation and execution contracts."""

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Callable, Mapping


@dataclass(frozen=True)
class SupervisorPlan:
    plan_id: str
    case_id: str
    trace_id: str
    plan_version: str
    nodes: tuple[dict, ...]
    final_agent: str = "advisor"
    edges: tuple[tuple[str, str], ...] = ()

    def validate(self) -> None:
        if not self.nodes or len(self.nodes) > 5:
            raise ValueError("supervisor plan must contain one to five nodes")
        ids = [str(node.get("step_id", "")) for node in self.nodes]
        if any(not step_id for step_id in ids) or len(set(ids)) != len(ids):
            raise ValueError("supervisor plan step_ids must be non-empty and unique")
        node_ids = set(ids)
        for node in self.nodes:
            if not node.get("agent") or not node.get("output_schema"):
                raise ValueError("each node requires agent and output_schema")
            if any(ref not in node_ids for ref in node.get("input_refs", ())):
                raise ValueError("node input_refs must reference existing steps")
        edges = set(self.edges)
        edges.update((ref, step_id) for node, step_id in zip(self.nodes, ids) for ref in node.get("input_refs", ()))
        allowed_targets = node_ids | ({"advisor"} if self.final_agent == "advisor" else set())
        if any(source not in node_ids or target not in allowed_targets for source, target in edges):
            raise ValueError("edges must reference existing steps or the advisor final sink")
        incoming = {step_id: 0 for step_id in ids}
        outgoing = {step_id: [] for step_id in ids}
        for source, target in edges:
            if target == "advisor":
                continue
            incoming[target] += 1
            outgoing[source].append(target)
        queue = [step_id for step_id, count in incoming.items() if count == 0]
        visited = 0
        while queue:
            current = queue.pop(0)
            visited += 1
            for target in outgoing[current]:
                incoming[target] -= 1
                if incoming[target] == 0:
                    queue.append(target)
        if visited != len(ids):
            raise ValueError("supervisor plan must be acyclic")
        if self.final_agent != "advisor" and self.final_agent not in {node.get("agent") for node in self.nodes}:
            raise ValueError("final_agent must be advisor or a planned agent")

    def ordered_nodes(self) -> tuple[dict, ...]:
        """Return a stable topological ordering without mutating the plan."""
        self.validate()
        by_id = {str(node["step_id"]): node for node in self.nodes}
        dependencies = {step_id: set(node.get("input_refs", ())) for step_id, node in by_id.items()}
        ordered: list[dict] = []
        ready = [str(node["step_id"]) for node in self.nodes if not dependencies[str(node["step_id"])]]
        while ready:
            current = ready.pop(0)
            ordered.append(by_id[current])
            for candidate in by_id:
                if current in dependencies[candidate]:
                    dependencies[candidate].remove(current)
                    if not dependencies[candidate] and candidate not in {str(node["step_id"]) for node in ordered} and candidate not in ready:
                        ready.append(candidate)
        return tuple(ordered)


AgentHandler = Callable[[Mapping[str, Any]], Any]


class AgentRegistry:
    """Explicit registry for structured expert-agent handlers.

    Handlers receive only the plan node's declared ``input_refs``. They do not
    receive container dependencies or a mutable plan, which keeps data access at
    the Tool Gateway and prevents agents from changing orchestration at runtime.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, AgentHandler] = {}

    def register(self, agent_id: str, handler: AgentHandler) -> None:
        if not agent_id:
            raise ValueError("agent id is required")
        if agent_id in self._handlers:
            raise ValueError(f"agent already registered: {agent_id}")
        self._handlers[agent_id] = handler

    def get(self, agent_id: str) -> AgentHandler:
        try:
            return self._handlers[agent_id]
        except KeyError as exc:
            raise ValueError(f"agent is not registered: {agent_id}") from exc


@dataclass(frozen=True)
class PlanExecutionResult:
    status: str
    outputs: Mapping[str, Any]
    failed_steps: Mapping[str, str]
    warnings: tuple[str, ...] = ()


class SupervisorExecutor:
    """Execute a validated plan with deterministic dependency and failure rules."""

    def __init__(self, agents: AgentRegistry) -> None:
        self.agents = agents

    def execute(self, plan: SupervisorPlan, *, initial_input: Mapping[str, Any] | None = None) -> PlanExecutionResult:
        plan.validate()
        outputs: dict[str, Any] = {}
        failures: dict[str, str] = {}
        warnings: list[str] = []
        root_input = MappingProxyType(dict(initial_input or {}))

        for node in plan.ordered_nodes():
            step_id = str(node["step_id"])
            refs = tuple(node.get("input_refs", ()))
            critical = bool(node.get("critical", True))
            missing = [ref for ref in refs if ref not in outputs]
            if missing:
                message = f"missing structured input from: {', '.join(missing)}"
                failures[step_id] = message
                if critical:
                    return PlanExecutionResult("blocked", MappingProxyType(outputs), MappingProxyType(failures), tuple(warnings))
                warnings.append(f"non-critical step {step_id} skipped: {message}")
                continue
            inputs = {ref: outputs[ref] for ref in refs}
            if not refs:
                inputs["request"] = root_input
            try:
                handler = self.agents.get(str(node["agent"]))
                outputs[step_id] = handler(MappingProxyType(inputs))
            except Exception as exc:  # Handlers are isolated; only stable failure text crosses the boundary.
                failures[step_id] = str(exc) or exc.__class__.__name__
                if critical:
                    return PlanExecutionResult("blocked", MappingProxyType(outputs), MappingProxyType(failures), tuple(warnings))
                warnings.append(f"non-critical step {step_id} failed")

        return PlanExecutionResult(
            "partial_success" if failures else "completed",
            MappingProxyType(outputs),
            MappingProxyType(failures),
            tuple(warnings),
        )
