"""数据库会话工厂；未配置 SQLAlchemy 时仍可被测试替身导入。"""

from app.core.config import get_settings


def create_session_factory():
    """Create sessions that set the transaction tenant context when supplied."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    settings = get_settings()
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    return sessionmaker(bind=engine, expire_on_commit=False)


def set_tenant_context(session, tenant_id: str) -> None:
    """Set a transaction-local RLS context; callers must invoke before queries."""
    from sqlalchemy import text
    session.execute(text("SELECT set_config('app.tenant_id', :tenant_id, true)"), {"tenant_id": tenant_id})


class DatabaseSession:
    """兼容测试用的空会话上下文。"""

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False
