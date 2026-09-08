import pytest

from app.db.cloud_bootstrap import validate_admin_connection_url
from app.db.cloud_seed import issuer_from_public_url
from app.db.engine import normalize_psycopg_url


def test_normalizes_app_platform_database_url() -> None:
    assert normalize_psycopg_url("postgresql://user:secret@private-db/workloop") == (
        "postgresql+psycopg://user:secret@private-db/workloop"
    )
    assert normalize_psycopg_url("postgresql+psycopg://user:secret@private-db/workloop") == (
        "postgresql+psycopg://user:secret@private-db/workloop"
    )


def test_rejects_non_postgresql_database_url() -> None:
    with pytest.raises(ValueError, match="PostgreSQL"):
        normalize_psycopg_url("sqlite:///workloop.db")


def test_accepts_exact_private_admin_database_url() -> None:
    value = (
        "postgresql://doadmin:secret@"
        "private-workloop.db.ondigitalocean.com:25060/workloop?sslmode=require"
    )
    assert validate_admin_connection_url(value, "workloop") == value


@pytest.mark.parametrize(
    "value",
    [
        "postgresql://other:secret@private-workloop.db.ondigitalocean.com:25060/"
        "workloop?sslmode=require",
        "postgresql://doadmin:secret@workloop.db.ondigitalocean.com:25060/workloop?sslmode=require",
        "postgresql://doadmin:secret@private-workloop.db.ondigitalocean.com:25060/"
        "keycloak?sslmode=require",
        "postgresql://doadmin:secret@private-workloop.db.ondigitalocean.com:25060/workloop",
    ],
)
def test_rejects_admin_database_url_outside_boundary(value: str) -> None:
    with pytest.raises(RuntimeError, match="approved boundary"):
        validate_admin_connection_url(value, "workloop")


def test_builds_cloud_issuer_from_exact_origin() -> None:
    assert issuer_from_public_url("https://workloop-test.ondigitalocean.app") == (
        "https://workloop-test.ondigitalocean.app/auth/realms/workloop-dev"
    )


@pytest.mark.parametrize(
    "value",
    [
        "http://workloop-test.ondigitalocean.app",
        "https://workloop-test.ondigitalocean.app/path",
        "https://other.example.com",
        "https://user@workloop-test.ondigitalocean.app",
    ],
)
def test_rejects_cloud_seed_origin_outside_boundary(value: str) -> None:
    with pytest.raises(RuntimeError, match="exact App Platform HTTPS origin"):
        issuer_from_public_url(value)
