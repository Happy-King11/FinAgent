"""数据库会话抽象和连接探针。"""

from sqlalchemy import text

from app.infrastructure.database.session import create_session_factory


def check_database() -> bool:
    try:
        factory = create_session_factory()
        with factory() as session:
            session.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001 - readiness reports dependency state.
        return False
