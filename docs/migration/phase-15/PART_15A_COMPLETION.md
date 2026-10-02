# Part 15A completion

Status: Part 15A is complete when every routed GitHub job for the commit containing this record
passes. The implementation and boundary-matched local gate passed on 2026-10-02.

## Result

Part 15A created the Phase 15 plan, portal integration contract, dependency inventory, golden cases,
machine catalogue, focused verifier, mutation tests, workflow route, roadmap update, and this
completion record.

The catalogue contains 52 integration items, 31 current API client contracts, 29 approved browser
routes, six file flows, eight owned gaps, and 42 golden cases. Every record has one owner from 15B
through 15H. The part sequence is 15A through 15H, and rollback is the exact reverse order.

The baseline decision is deliberately narrow. Phase 15 will route and test the current product. It
will not add a backend business action to fill a browser gap. Unsupported actions remain absent or
use the stable unavailable state. FastAPI authorization remains authoritative, and route visibility
does not count as permission proof.

## Inventory findings

The repository already has the OIDC session, protected HTTP client, server-derived account, company
and branch context, 31 domain clients, and role-aware product views. The integration problem is the
entry and composition. `src/App.jsx` still presents `Architecture proof`, and
`src/OrganizationPanel.jsx` renders most signed-in views in one long document.

The eight owned gaps are the missing shell and route denials, ungrouped administrator views, mixed
manager concerns, missing employee navigation, missing route-oriented product and quality proof, the
live architecture-proof page, missing live portal recovery and performance acceptance, and the
missing independent Phase 15 verdict.

Part 15B owns only the shared shell, session routing, role home selection, branch context, common
navigation states, and removal of the storage proof from product navigation. Parts 15C, 15D, and 15E
own the administrator, manager, and employee portals. Part 15F owns local product, denial,
accessibility, and performance proof. Part 15G owns reviewed DigitalOcean promotion and live
acceptance. Part 15H owns the independent review and phase signoff request.

## Focused verification

The focused checks passed:

- `verify-phase-15a-contract.mjs` reported 52 inventory items, 31 client contracts, 29 routes, six
  file flows, eight gaps, 42 golden cases, and seven later-part owners;
- all 11 Part 15A tests passed, including ten mutations for duplicate IDs, owner loss, invalid action
  and evidence, rollback drift, invented endpoints, unknown roles, duplicate paths, wrong route
  ownership, missing file delivery, prose drift, schema drift, and deployment drift;
- the Phase 14H verifier still traced all 57 Phase 14 inventory items and 38 golden cases with one
  Alembic head;
- all 13 workflow classification and phase-execution tests passed;
- focused ESLint passed; and
- the prose and changed-file whitespace audits passed.

## Boundary-matched local gate

The workflow route makes 15A full-stack sensitive. The complete local gate passed in the fresh
`workloop-phase15a-verify` environment.

The gate ran 369 Node tests and 704 backend tests. The locked production build passed. Backend lint,
formatting, strict type checks, and dependency checks passed. Pyright reported zero errors and the
locked environment reported no broken requirements.

The stack applied migrations twice, downgraded an empty schema to base, replayed the complete chain,
and confirmed the single head at `e8a1c3f5b7d9`. The Phase 15A verifier also confirmed the indexed
Alembic digest stayed at `e5476fe6af02cb5ac3387e0da5ea252b39eb6eadbaf10c9db0a75280c3acbda2`.

HTTP boundary checks passed. Keycloak configuration passed twice, followed by authentication and
realm checks. The gate recorded database, signing-key, storage, and scanner state, restarted the same
images without removing their volumes, and reproduced every recorded value. The complete synthetic
administrator, manager, employee, and file browser journey passed after restart.

The browser verifier removed every synthetic application row and Keycloak identity by exact
identifier. The final database and identity counts were zero, and the safe-log check passed. Cleanup
removed only the `workloop-phase15a-verify` containers, network, and three volumes.

## Unchanged boundaries

Part 15A changed no React runtime, FastAPI route, backend service, schema revision, RLS policy, grant,
protected function, Compose definition, Keycloak configuration source, Terraform source, live
setting, credential, or DigitalOcean resource. It used no real record or private object.

DigitalOcean remains the only provider. Automatic deployment remains disabled, and the
provider-managed App Platform default address remains the only approved public address. The
`workloop-clinic-dev` project, `fra1-default` network, Phase 13 external archive, and
`workloop-clinic_postgres_data` remain preserved. The protected local volume was not attached,
mounted, inspected, modified, deleted, or recreated.

## Rollback and continuation

Part 15A rollback removes its Phase 15 records, verifier, tests, package command, workflow route, and
roadmap update. It does not change runtime, database, identity, provider, or business data.

After the routed GitHub jobs pass and the branch is clean and synchronized, Part 15B runs in a new
Codex task. It replaces the architecture-proof landing view with the shared portal shell and session
routing. It must not implement the administrator portal assigned to 15C or add a backend business
capability.
