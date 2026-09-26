# Retired source-system SQL

Historical record. Do not run or deploy these files.

This directory preserves the Supabase SQL that existed before the portable Alembic schema became
the only database definition. `root/` contains the former repository-root files. `numbered/`
contains the former `sql/` chain. Neither directory is part of database bootstrap, migration,
testing, or deployment.

Current schema changes belong in a new append-only revision under `backend/alembic/versions/`.
Do not copy statements from these files into a current migration without reviewing them against the
current authorization, ownership, and tenant boundaries.
