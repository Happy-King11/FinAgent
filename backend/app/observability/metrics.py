"""最小指标接口；生产可替换为 Prometheus client。"""

from collections import Counter


class Metrics:
    def __init__(self):
        self.counters = Counter()

    def inc(self, name: str, value: int = 1) -> None:
        self.counters[name] += value
