# Source-system terms in backend evidence

Historical record. Do not run or deploy these files.

Two append-only Alembic revisions retain Supabase terminology because their comments explain the
source schema that the portable database replaced:

- `alembic/versions/9f3c7b5d2a18_add_retained_business_functions.py`
- `alembic/versions/a0d4e6f8c92b_add_runtime_grants.py`

The revisions must not be rewritten. `tests/test_phase4_schema.py` and
`tests/test_seed_fixtures.py` also keep inert assertions that prove the current database has no
source-system roles, schemas, or fixtures. These names are historical evidence, not runtime
configuration.
