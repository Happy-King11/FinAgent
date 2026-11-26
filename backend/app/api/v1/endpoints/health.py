"""健康检查端点的兼容导出。"""

from app.api.v1.router import live, ready

__all__ = ["live", "ready"]
