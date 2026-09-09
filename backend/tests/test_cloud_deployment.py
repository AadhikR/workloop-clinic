import pytest

from app.db import cloud_migrate
from app.db.cloud_bootstrap import BOOTSTRAPS, validate_admin_connection_url
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


def test_cloud_bootstrap_grants_only_approved_database_connections() -> None:
    bootstraps = {bootstrap.database: bootstrap for bootstrap in BOOTSTRAPS}

    workloop_roles = bootstraps["workloop"].connect_roles
    assert [(role.name, role.inherit) for role in workloop_roles] == [
        ("workloop_runtime", True),
        ("workloop_expiry_processing", False),
    ]
    assert bootstraps["keycloak"].connect_roles == ()


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


def test_cloud_migration_runs_every_stage_in_order(monkeypatch: pytest.MonkeyPatch) -> None:
    stages: list[str] = []
    monkeypatch.setattr(cloud_migrate.cloud_bootstrap, "main", lambda: stages.append("bootstrap"))
    monkeypatch.setattr(cloud_migrate, "upgrade_schema", lambda: stages.append("alembic"))
    monkeypatch.setattr(cloud_migrate.cloud_seed, "main", lambda: stages.append("seed"))

    assert cloud_migrate.main() == 0
    assert stages == ["bootstrap", "alembic", "seed"]


def test_cloud_migration_stops_before_seed_when_upgrade_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stages: list[str] = []
    monkeypatch.setattr(cloud_migrate.cloud_bootstrap, "main", lambda: stages.append("bootstrap"))

    def fail_upgrade() -> None:
        stages.append("alembic")
        raise RuntimeError("upgrade failed")

    monkeypatch.setattr(cloud_migrate, "upgrade_schema", fail_upgrade)
    monkeypatch.setattr(cloud_migrate.cloud_seed, "main", lambda: stages.append("seed"))

    with pytest.raises(RuntimeError, match="upgrade failed"):
        cloud_migrate.main()
    assert stages == ["bootstrap", "alembic"]
