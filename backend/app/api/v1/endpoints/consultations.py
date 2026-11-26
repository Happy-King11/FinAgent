"""咨询创建和查询端点的兼容导出。"""

from app.api.v1.router import create_consultation, get_consultation

__all__ = ["create_consultation", "get_consultation"]
