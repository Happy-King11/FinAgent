"""产品查询端点的兼容导出。"""

from app.api.v1.router import get_product, list_products

__all__ = ["get_product", "list_products"]
