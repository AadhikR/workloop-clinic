"""Synthetic development fixtures for the migrated schema (Phase 4E).

The seed is deterministic, idempotent, and free of real personal data. It is not
part of the Alembic upgrade path. Run it with ``python -m app.db.seed``.
"""

from app.db.seed.runner import apply_rows, build_rows, clean, main, validate

__all__ = ["apply_rows", "build_rows", "clean", "main", "validate"]
