"""Database initialization helpers for local development and deployment checks."""

from pathlib import Path

from sqlalchemy import text

from app.core.config import get_settings
from app.infrastructure.database.session import create_session_factory


MIGRATION_DIR = Path(__file__).resolve().parents[1] / "migrations"


def apply_migrations() -> list[str]:
    """Apply the repository's idempotent SQL migrations in lexical order."""
    session_factory = create_session_factory()
    applied: list[str] = []
    with session_factory() as session:
        for path in sorted(MIGRATION_DIR.glob("*.sql")):
            sql = path.read_text(encoding="utf-8")
            # PostgreSQL accepts multi-statement migration files through exec_driver_sql.
            session.connection().exec_driver_sql(sql)
            applied.append(path.name)
        session.commit()
    return applied


def check_database() -> bool:
    try:
        session_factory = create_session_factory()
        with session_factory() as session:
            session.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001 - readiness converts infrastructure failures to false.
        return False


if __name__ == "__main__":
    if get_settings().app_env == "production" and not check_database():
        raise SystemExit("database is unavailable")
    print("applied:", ", ".join(apply_migrations()))
