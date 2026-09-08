import os

from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool

from alembic import context
from app.db.engine import normalize_psycopg_url
from app.models import Base

target_metadata = Base.metadata


def migration_database_url() -> str:
    database_url = os.environ.get("MIGRATION_DATABASE_URL")
    if not database_url:
        raise RuntimeError("MIGRATION_DATABASE_URL is required")
    try:
        return normalize_psycopg_url(database_url)
    except ValueError as error:
        raise RuntimeError("MIGRATION_DATABASE_URL must use PostgreSQL") from error


def run_migrations_offline() -> None:
    context.configure(
        url=migration_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_server_default=True,
        compare_type=True,
        transaction_per_migration=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(migration_database_url(), poolclass=NullPool)
    try:
        with engine.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                compare_server_default=True,
                compare_type=True,
                transaction_per_migration=True,
            )

            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
