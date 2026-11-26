"""Redis 客户端工厂；缓存不可作为唯一业务数据源。"""

from app.core.config import get_settings


def create_redis_client():
    from redis import Redis
    return Redis.from_url(get_settings().redis_url, decode_responses=True)
