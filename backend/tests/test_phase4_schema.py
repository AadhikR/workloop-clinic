"""Static Phase 4 schema guarantees that need no database.

These cover the metadata-level guarantees the Phase 4C completion gate requires:
foreign keys resolve across the whole target schema, no column keeps a legacy
Supabase ownership shape, and neither the models nor the migrations mention
``auth.users`` or any other Supabase-era identity or storage object.
"""

import re
from pathlib import Path

import pytest

from app.models import Base
from tests.test_db_base import PHASE_4_TARGET_TABLES

BACKEND_ROOT = Path(__file__).resolve().parent.parent
MODEL_DIR = BACKEND_ROOT / "app" / "models"
MIGRATION_DIR = BACKEND_ROOT / "alembic" / "versions"
SEED_DIR = BACKEND_ROOT / "app" / "db" / "seed"

# Substrings that would mean a migrated column or expression still points at a
# Supabase-era identity, role, or storage object instead of the app-user model.
FORBIDDEN_PATTERNS = (
    ("auth schema", re.compile(r"\bauth\s*\.")),
    ("storage schema", re.compile(r"\bstorage\s*\.")),
    ("legacy auth-user column", re.compile(r"\bauth_user_id\b")),
    (
        "Supabase service role",
        re.compile(
            r"\b(?:service_role|supabase_admin|supabase_auth_admin|"
            r"supabase_storage_admin|authenticator|dashboard_user)\b"
        ),
    ),
    ("Supabase browser role", re.compile(r"['\"](?:anon|authenticated)['\"]")),
    (
        "Supabase browser role grant",
        re.compile(
            r"\b(?:grant|revoke|set\s+role|create\s+role|alter\s+role|drop\s+role)\b"
            r"[^;\n]*(?:\banon\b|\bauthenticated\b)"
        ),
    ),
)

SCANNED_FILES = sorted(
    path
    for path in (
        *MODEL_DIR.glob("*.py"),
        *MIGRATION_DIR.glob("*.py"),
        *SEED_DIR.glob("*.py"),
    )
    if path.name != "__init__.py"
)


def test_scan_corpus_is_non_empty() -> None:
    # A silent empty glob would make the negative scans vacuously pass.
    model_files = {path.name for path in SCANNED_FILES if path.parent == MODEL_DIR}
    assert {"identity.py", "payroll.py", "leave.py", "attendance.py", "records.py"} <= model_files
    assert sum(1 for path in SCANNED_FILES if path.parent == MIGRATION_DIR) >= 7


@pytest.mark.parametrize("path", SCANNED_FILES, ids=lambda path: path.name)
def test_no_supabase_identity_or_storage_references(path: Path) -> None:
    text = path.read_text(encoding="utf-8").lower()
    hits = [label for label, pattern in FORBIDDEN_PATTERNS if pattern.search(text)]
    assert not hits, f"{path.name} still references {hits}"


def test_no_column_keeps_a_legacy_ownership_shape() -> None:
    offenders: list[str] = []
    for table in Base.metadata.tables.values():
        for column in table.columns:
            name = column.name
            if name == "user_id" or name.endswith("auth_user_id"):
                offenders.append(f"{table.name}.{name}")
    assert not offenders, f"legacy ownership columns survived: {offenders}"


def test_every_foreign_key_resolves_within_the_target_schema() -> None:
    for table in Base.metadata.tables.values():
        for fk in table.foreign_keys:
            # Accessing .column forces SQLAlchemy to resolve the reference; an
            # unresolved target raises here rather than at first query.
            target_table = fk.column.table.name
            assert target_table in PHASE_4_TARGET_TABLES, (
                f"{table.name}.{fk.parent.name} points outside the target schema: {target_table}"
            )


def test_actor_references_use_the_app_user_identity() -> None:
    # Trusted actor and recipient columns must carry the _app_user_id suffix so
    # they resolve to app_users (directly or through user_profiles), never to a
    # bare Supabase owner id.
    for table in Base.metadata.tables.values():
        for fk in table.foreign_keys:
            if fk.column.table.name in {"app_users", "user_profiles"} and fk.column.name in {
                "id",
                "app_user_id",
            }:
                assert fk.parent.name.endswith("app_user_id"), (
                    f"{table.name}.{fk.parent.name} references an identity table "
                    "without the app-user naming shape"
                )
