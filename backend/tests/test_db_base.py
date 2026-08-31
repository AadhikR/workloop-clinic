from app.db.base import NAMING_CONVENTION, Base


def test_foundation_metadata_has_no_business_tables() -> None:
    assert list(Base.metadata.tables) == []


def test_foundation_metadata_has_deterministic_constraint_names() -> None:
    assert NAMING_CONVENTION == {
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    }
