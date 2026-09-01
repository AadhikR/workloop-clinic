from app.db.base import NAMING_CONVENTION, Base
from app.models.identity import AccountStatus, AppRole


def test_identity_metadata_contains_only_phase_4b_tables() -> None:
    assert list(Base.metadata.tables) == [
        "companies",
        "branches",
        "employees",
        "app_users",
        "user_profiles",
    ]


def test_foundation_metadata_has_deterministic_constraint_names() -> None:
    assert NAMING_CONVENTION == {
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    }


def test_identity_enums_match_the_approved_design() -> None:
    assert [status.value for status in AccountStatus] == [
        "pending_identity",
        "active",
        "disabled",
    ]
    assert [role.value for role in AppRole] == ["admin", "manager", "employee"]
