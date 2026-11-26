"""工具调用的超时、重试和简易熔断策略。"""

from dataclasses import dataclass
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from typing import Any, Callable


@dataclass
class CircuitBreaker:
    failure_threshold: int = 5
    cooldown_seconds: int = 30
    failures: int = 0
    opened_at: float | None = None

    def allow(self) -> bool:
        return self.opened_at is None or time.monotonic() - self.opened_at >= self.cooldown_seconds

    def success(self) -> None:
        self.failures = 0
        self.opened_at = None

    def failure(self) -> None:
        self.failures += 1
        if self.failures >= self.failure_threshold:
            self.opened_at = time.monotonic()


def call_with_retry(fn: Callable[..., Any], *, attempts: int = 2, timeout_seconds: float = 5, breaker: CircuitBreaker | None = None, idempotent: bool = True, **kwargs: Any) -> Any:
    """执行只读/幂等工具；副作用工具不得自动重试。"""
    breaker = breaker or CircuitBreaker()
    if not breaker.allow():
        raise TimeoutError("tool circuit breaker is open")
    max_attempts = attempts if idempotent else 1
    last_error: Exception | None = None
    for _ in range(max_attempts):
        try:
            # future.result(timeout=...) 防止慢工具阻塞整个咨询请求线程。
            executor = ThreadPoolExecutor(max_workers=1)
            future = executor.submit(fn, **kwargs)
            try:
                result = future.result(timeout=timeout_seconds)
            finally:
                # 线程无法强制终止，但取消未开始任务并立即释放调用方等待。
                executor.shutdown(wait=False, cancel_futures=True)
            breaker.success()
            return result
        except FutureTimeout as exc:
            last_error = TimeoutError("tool call timed out")
            breaker.failure()
        except Exception as exc:  # noqa: BLE001 - reliability layer records and retries provider errors.
            last_error = exc
            breaker.failure()
    raise last_error or RuntimeError("tool call failed")
