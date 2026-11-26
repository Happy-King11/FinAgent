"""Lifecycle hooks with observer isolation."""

from dataclasses import dataclass, field
from typing import Any, Protocol

from app.runtime.context import RuntimeContext


class LifecycleHook(Protocol):
    def before_run(self, context: RuntimeContext) -> None: ...
    def after_route(self, context: RuntimeContext, route: Any) -> None: ...
    def before_step(self, context: RuntimeContext, step: str) -> None: ...
    def after_step(self, context: RuntimeContext, step: str, result: Any) -> None: ...
    def on_quality_failure(self, context: RuntimeContext, failure: Any) -> None: ...
    def on_retry(self, context: RuntimeContext, failure: Any) -> None: ...
    def on_fallback(self, context: RuntimeContext, failure: Any) -> None: ...
    def on_compliance_block(self, context: RuntimeContext, result: Any) -> None: ...
    def on_human_review(self, context: RuntimeContext, result: Any) -> None: ...
    def on_state_transition(self, context: RuntimeContext, transition: Any) -> None: ...
    def on_error(self, context: RuntimeContext, failure: Any) -> None: ...
    def after_run(self, context: RuntimeContext, result: Any) -> None: ...
    def finally_run(self, context: RuntimeContext) -> None: ...


@dataclass
class HookDiagnostics:
    failures: list[dict[str, str]] = field(default_factory=list)


class NoopHook:
    def __getattr__(self, name: str):
        if name.startswith(("before_", "after_", "on_", "finally")):
            return lambda *args, **kwargs: None
        raise AttributeError(name)


class HookRunner:
    def __init__(self, hooks: tuple[LifecycleHook, ...] = (), *, diagnostics: HookDiagnostics | None = None) -> None:
        self.hooks = tuple(hooks)
        self.diagnostics = diagnostics or HookDiagnostics()

    def run(self, method: str, *args: Any) -> None:
        for hook in self.hooks:
            callback = getattr(hook, method, None)
            if callback is None:
                continue
            try:
                callback(*args)
            except Exception as exc:
                self.diagnostics.failures.append({"hook": method, "type": type(exc).__name__})

    def before_run(self, context: RuntimeContext) -> None: self.run("before_run", context)
    def after_route(self, context: RuntimeContext, route: Any) -> None: self.run("after_route", context, route)
    def before_step(self, context: RuntimeContext, step: str) -> None: self.run("before_step", context, step)
    def after_step(self, context: RuntimeContext, step: str, result: Any) -> None: self.run("after_step", context, step, result)
    def on_quality_failure(self, context: RuntimeContext, failure: Any) -> None: self.run("on_quality_failure", context, failure)
    def on_retry(self, context: RuntimeContext, failure: Any) -> None: self.run("on_retry", context, failure)
    def on_fallback(self, context: RuntimeContext, failure: Any) -> None: self.run("on_fallback", context, failure)
    def on_compliance_block(self, context: RuntimeContext, result: Any) -> None: self.run("on_compliance_block", context, result)
    def on_human_review(self, context: RuntimeContext, result: Any) -> None: self.run("on_human_review", context, result)
    def on_state_transition(self, context: RuntimeContext, transition: Any) -> None: self.run("on_state_transition", context, transition)
    def on_error(self, context: RuntimeContext, failure: Any) -> None: self.run("on_error", context, failure)
    def after_run(self, context: RuntimeContext, result: Any) -> None: self.run("after_run", context, result)
    def finally_run(self, context: RuntimeContext) -> None: self.run("finally_run", context)
