# Phase 7H completion record

## Status at commit preparation

The project owner authorized Phase 7H on 2026-09-12. The independent review, its correction, the
seven cutover evidence refreshes, and the complete local Phase 7 gate are finished. The matching
GitHub Actions result and explicit project-owner Phase 7 signoff remain external completion gates.

Phase 8 remains unauthorized.

## Independent review result

The independent review traced all 24 stable Phase 7A dependency IDs through the seven cutover
records. Every replacement locator names an existing file, no `synthetic://` locator remains, and
all later-phase dependencies have an explicit owner.

The review found one blocking defect: exported legacy `deleteEmployee` still performed a Supabase
hard delete even though the approved Phase 7 contract excludes employee hard deletion. The export
now fails before any Supabase call, the employee-administration freeze declaration names the hard
delete, and a regression test proves that the function contains no Supabase path.

The review also recorded a retained legacy limitation. Phase 11 contract handling and other
later-phase screens still use shared legacy functions that Phase 7 froze. Those screens are absent
from the migration build and remain owned by their named later phases. Phase 7H did not change their
transactions or pull later work into Phase 7.

No finding required a schema, role, grant, protected-function, rollback, phase-boundary, or Alembic
change. Alembic remains at the single head `8f6b2d1a4c70`.

## Cutover proof

All seven cutover records validate with completed state, one writable system, an opposite-system
freeze, and rollback steps in the required order. Their synthetic evidence was refreshed at
`2026-09-12T17:05:40Z` after the settled local gate.

The fresh business-state results were:

| Cutover unit | Synthetic result |
| --- | --- |
| Organization context | Database state `4a0731e2e75bb0a0e534227af6500ebe64dc2ed9ad19ffe0fb8d315311fc18e3` remained unchanged. |
| Organization administration | `dd5e4f94ae8c89f41e738b8fe29f80f1e9a975bf49626f377ebd594fb9e68b55` |
| Employee directory | `f0e5c707700cbbcd8cf447c313370a1377a77b925df7a75e7f04b79eb33dede4` |
| Departments | `48bd1478157986dfe2a009b9f70ec9e39836c0f7d20d61069447cc4d6e8efb16` |
| Staffing rules | `48bd1478157986dfe2a009b9f70ec9e39836c0f7d20d61069447cc4d6e8efb16` |
| Employee administration | `33c86d55e25f7bc766f1677a39214b233bc5edaf2c6e86ff036e3113a99f7f5f` |
| Employee lifecycle | `3936a6ed48373e102be656033bab15924cb4dc16c363885a72ec07d5346f2740` |

The focused Phase 7H test independently proves the exact 24-ID union, all seven feature IDs,
concrete replacement locators, single-writer declarations, freeze direction, and rollback order.

## Complete local gate

The settled gate ran once in Compose project `workloop-phase7h-final` with a new temporary PostgreSQL
volume. It passed:

- 432 backend tests, Ruff lint and formatting, strict Pyright, and the locked dependency check;
- 119 frontend tests, both production builds, and isolation across 449 legacy modules and 36
  migration modules;
- repeatable migration at `8f6b2d1a4c70`, empty-schema downgrade and upgrade, no pending Alembic
  operations, exact Phase 7G predecessor restoration, and the full Phase 5F and Phase 5G revision
  chains;
- schema, migration round-trip, trigger, seed, repository, transaction-context, RLS, grant,
  protected-function, function-security, concurrency, audit, ownership, and PostgreSQL boundary
  checks;
- all Phase 7 organization, employee, department, staffing, administration, and lifecycle
  verifiers;
- API health, the Phase 6 HTTP and CORS boundary, idempotent Keycloak configuration, two expected
  Keycloak realms, and Keycloak-to-FastAPI authentication; and
- the complete administrator, manager, and employee browser journey after restart, final service
  log safety, and complete synthetic-data cleanup.

The backend quality gate used a disposable Python 3.12.10 environment with the locked project
dependencies. The repository's local Windows virtual environment was stale and was not used.

## Restart and rollback proof

The stack was stopped without removing data and recreated from the existing images. The database
catalogue fingerprint remained `3dcb949149dcb3078cd841a51bf9e6ff`, both Keycloak signing key IDs
remained unchanged, and each image ID matched its pre-restart value:

- PostgreSQL: `sha256:051f7b7b3abdd564d5d1bd1e8c4b9c1b6e77087d1dd22020ede611c096a272e0`;
- backend: `sha256:335a557808c085464a158a0477f9af2d9628f877fa7a56a64545e807126860d0`;
  and
- Keycloak: `sha256:9d1f1b2b7261ff53c66cb1092dfcdc34a5fb77e81f9e6a6e75b8b6a795de8067`.

The exact Phase 7G predecessor-state hash before and after its downgrade round trip was
`ba257198f905a96014a8268ffd3da90197cdbc762e954ee69150860b3a9254db`. The older Phase 5D, Phase 5E,
Phase 5F, and Phase 5G rollback boundaries also returned to their expected states and restored the
current head.

## Resource boundary

Verification used synthetic local data only. It accessed no production data, cloud resource, paid
service, or persistent external credential. The Phase 7H containers, network, generated local
credentials, and temporary volume `workloop-phase7h-final_postgres_data` were removed after the
gate.

The protected `workloop-clinic_postgres_data` volume was not attached to the Phase 7H stack,
upgraded, recreated, seeded, or deleted. It remains present. The retained empty FRA1 default VPC
was not changed.

## Stop condition

Do not start Phase 8. First require the matching GitHub Actions result and explicit project-owner
Phase 7 signoff. Phase 8 requires separate authorization even after Phase 7 is signed off.
