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
        "OIDC_ISSUER": "http://127.0.0.1:8080/realms/workloop-dev",
        "OIDC_AUDIENCE": "workloop-api",
        "OIDC_JWKS_URL": (
            "http://127.0.0.1:8080/realms/workloop-dev/protocol/openid-connect/certs"
        ),
        "OIDC_JWKS_CONNECT_TIMEOUT_SECONDS": "2",
        "OIDC_JWKS_READ_TIMEOUT_SECONDS": "2",
        "OIDC_JWKS_TOTAL_TIMEOUT_SECONDS": "5",
        "OIDC_JWKS_CACHE_TTL_SECONDS": "300",
        "OIDC_JWKS_REFRESH_COOLDOWN_SECONDS": "1",
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


@pytest.mark.parametrize("app_env", ["development", "staging", "production"])
def test_deployed_settings_require_https_oidc_urls(monkeypatch: MonkeyPatch, app_env: str) -> None:
    set_required_environment(monkeypatch)
    monkeypatch.setenv("APP_ENV", app_env)

    with pytest.raises(ValidationError, match="must use HTTPS"):
        Settings()  # pyright: ignore[reportCallIssue]


def test_deployed_settings_accept_https_oidc_urls(monkeypatch: MonkeyPatch) -> None:
    set_required_environment(monkeypatch)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("OIDC_ISSUER", "https://identity.example.test/realms/workloop")
    monkeypatch.setenv(
        "OIDC_JWKS_URL", "https://identity.example.test/realms/workloop/openid-connect/certs"
    )

    settings = Settings()  # pyright: ignore[reportCallIssue]

    assert settings.oidc_issuer.scheme == "https"


def test_settings_reject_oidc_url_credentials(monkeypatch: MonkeyPatch) -> None:
    set_required_environment(monkeypatch)
    monkeypatch.setenv(
        "OIDC_JWKS_URL",
        "http://user:password@127.0.0.1:8080/realms/workloop-dev/certs",
    )

    with pytest.raises(ValidationError, match="must not contain credentials"):
        Settings()  # pyright: ignore[reportCallIssue]
