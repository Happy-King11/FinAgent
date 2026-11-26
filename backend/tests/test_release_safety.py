"""Release and production safety contract tests."""

import os

import pytest

from app.core.config import Settings


def test_production_settings_reject_memory_vector_backend():
    with pytest.raises(ValueError, match="persistent storage"):
        Settings(
            app_env="production",
            auth_dev_mode=False,
            allow_memory_fallback=False,
            persistence_backend="postgresql",
            vector_store_backend="memory",
            jwt_hs256_secret="runtime-secret",
        )


def test_production_settings_require_jwt_and_non_memory_persistence():
    with pytest.raises(ValueError, match="JWT"):
        Settings(
            app_env="production",
            auth_dev_mode=False,
            allow_memory_fallback=False,
            persistence_backend="postgresql",
            vector_store_backend="qdrant",
        )


def test_runtime_environment_does_not_contain_repository_secrets():
    for name, value in os.environ.items():
        if name.endswith(("API_KEY", "SECRET", "PASSWORD")):
            assert value not in {"change-me", "change-me-too", "password"}
