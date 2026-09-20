# Part 10B completion

Status: complete.

## Result

Part 10B moves attendance settings, shift templates, and effective-dated shift assignments to
selected-branch FastAPI authority. Administrators can read and update redacted settings, list and
manage shift templates, and list or create effective assignments. Managers and employees receive no
new configuration authority. The migration client validates exact camelCase projections, uses
idempotency keys and optimistic timestamps for mutations, and does not accept browser-derived
company, branch, actor, or secret state.

The append-only Alembic revision `a6c8e0f2b4d7` adds the approved day, bounds, secret, shift-shape,
assignment timestamp, index, overlap, replay-resource, and protected-audit changes. Its downgrade
restores the exact Phase 9H predecessor, including removal of the `btree_gist` extension owned by
this revision. SQLAlchemy metadata and the historical database verifiers track the new head without
changing the Phase 9 exact-predecessor definitions.

The legacy attendance-settings, shift, deactivation, and assignment writers fail closed. Legacy
readers needed by later unauthorized Phase 10 screens remain available only to those legacy screens;
they are not a fallback for the migration configuration screen.

## Authority and rollback

The `attendance-configuration` cutover is complete. `migration-fastapi` is the sole read and write
authority for the migrated configuration surface, and its evidence digest validates. Rollback
freezes migration writes before restoring one legacy writer, then restores reads and verifies
authority and synthetic data. No shift or assignment history is deleted to recover authority.

## Gate evidence

The final tree passed the boundary-matched local gate in the isolated
`workloop-phase10b-gate` stack:

- Ruff lint and formatting, Pyright, dependency checks, and all 508 backend tests;
- all 185 frontend unit tests, the legacy production build, and the migration production build;
- repeatable migration, downgrade to base and upgrade to head, the Phase 5D through 5G historical
  replay, every Phase 8F through 10B exact-predecessor replay, and a clean Alembic head-drift check;
- the complete schema, seed, RLS, grant, security, employee-lifecycle, leave, expense, advance,
  payroll, WPS, Nafis, and Phase 10B database boundary suite;
- service health, HTTP boundaries, two Keycloak configuration passes, realm isolation, initial and
  final log-safety scans, storage reconciliation, database and signing-key persistence, and
  transaction-context isolation after a container restart; and
- the complete Keycloak and FastAPI authentication verifier, the Playwright browser-authentication
  suite, and final synthetic-data cleanup.

The routed GitHub result is reported in the task handoff after the single push; this pre-push record
does not contain a pending URL.

## Resource boundary

Verification used synthetic local data. The protected volume `workloop-clinic_postgres_data` was
not attached, modified, deleted, or recreated. Its creation timestamp remained
`2026-08-31T07:31:48Z` before and after the gate. The temporary stack was stopped without deleting
its isolated verification volume.

## Writing review

The repository-required `.opencode/skill/unslop/SKILL.md` was absent. All new prose received a
manual review for direct language, concrete claims, sentence-case headings, and consistent terms.

## Stop condition

Part 10C is next but remains unauthorized. This completion record does not authorize event
ingestion, biometric mapping, attendance calculation, corrections, period close, roster work,
swaps, or any other later Phase 10 implementation.
