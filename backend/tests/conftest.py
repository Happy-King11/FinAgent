"""Shared test configuration for the explicit development-auth profile."""

import os

import pytest


def pytest_configure(config):
    """Set the explicit development profile before application modules import."""
    os.environ.setdefault("APP_ENV", "development")
    os.environ["AUTH_DEV_MODE"] = "true"
    os.environ["REQUIRE_AUTH"] = "true"
    os.environ["PERSISTENCE_BACKEND"] = "memory"
    os.environ["VECTOR_STORE_BACKEND"] = "memory"
    os.environ["EMBEDDING_PROVIDER"] = "hashing"
    os.environ["LLM_BASE_URL"] = ""
    os.environ["REDIS_IDEMPOTENCY_ENABLED"] = "false"
    os.environ["OBJECT_STORAGE_ENABLED"] = "false"

    from app.core.config import get_settings

    get_settings.cache_clear()


@pytest.fixture(scope="session", autouse=True)
def configure_test_environment():
    yield
    from app.core.config import get_settings
    get_settings.cache_clear()
