import pytest
from pydantic import ValidationError
from pytest import MonkeyPatch

from app.core.config import Settings


def set_required_environment(monkeypatch: MonkeyPatch) -> None:
    values = {
        "APP_ENV": "test",
        "APP_BASE_URL": "http://127.0.0.1:8000",
        "FRONTEND_URL": "http://127.0.0.1:5173",
        "LOG_LEVEL": "INFO",
        "DATABASE_HEALTH_TIMEOUT_SECONDS": "5",
        "DATABASE_URL": "postgresql+psycopg://workloop_runtime:test-secret@postgres/workloop",
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)


def test_settings_hide_database_url(monkeypatch: MonkeyPatch) -> None:
    set_required_environment(monkeypatch)
    settings = Settings()  # pyright: ignore[reportCallIssue]

    assert "test-secret" not in repr(settings)


def test_settings_reject_non_postgresql_database(monkeypatch: MonkeyPatch) -> None:
    set_required_environment(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", "sqlite:///workloop.db")

    with pytest.raises(ValidationError, match=r"postgresql\+psycopg"):
        Settings()  # pyright: ignore[reportCallIssue]
