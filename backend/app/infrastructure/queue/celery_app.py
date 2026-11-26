"""Celery 应用工厂；Worker 与 API 使用相同 broker 配置。"""

from app.core.config import get_settings


def create_celery_app():
    from celery import Celery
    settings = get_settings()
    return Celery("financial_agent", broker=settings.worker_broker_url, backend=settings.worker_result_backend)
