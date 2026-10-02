# Part 15F completion

Status: Part 15F is complete when every routed GitHub job for the commit containing this record
passes. The implementation and complete local gate passed on 2026-10-02.

## Result

Part 15F adds a repeatable local acceptance gate for the administrator, manager, and employee
portals. The gate opens all 25 completed route groups, checks server-enforced denial boundaries,
exercises the six protected file and rendered-output flows, verifies accessibility and recovery,
measures the named performance profile, recreates the local stack without removing its data, scans
service logs, and removes only the synthetic gate resources.

The existing Phase 3G browser verifier now follows the routed portal instead of the retired
single-page layout. It still proves real Keycloak login, server-derived role and branch context,
cross-role denial, backend authorization, logout, browser history, and synthetic cleanup. The new
Phase 15F browser check covers the route shell and completed route groups without granting any new
browser authority.

## Fail-closed decisions

The route checks use the existing server-derived account, role, company, branch, manager, employee,
record, and file boundaries. A visible route or control is never treated as authorization. Cross-role
navigation stops before protected domain requests, and the database verifiers retain the backend
ownership and scope checks for attachments, receipts, records, assets, evidence, payslips, and
rendered outputs.

The notification dialog now closes on Escape, moves focus into the dialog when it opens, and returns
focus to its trigger when it closes. The trigger exposes its expanded and popup state. File and period
controls now have explicit accessible names. These changes affect interaction semantics only; they do
not add a request, field, permission, or business action.

The performance gate uses a named local-loopback Chromium profile with fixed budgets. It fails when
any compressed-transfer, route-change, form-feedback, or representative API measurement exceeds its
budget. It does not weaken the budget to accommodate a slow run.

Cleanup is restricted to the exact `workloop-phase15f-verify` Compose project and its three named
volumes. The pre-existing `workloop-clinic_postgres_data` volume was never attached and remained
present after cleanup. No broad container, network, volume, database, identity, or cloud cleanup was
used.

## Complete local gate

The frontend gate passed 395 Node tests, ESLint on every changed JavaScript and JSX file, and the
locked production build. The build transformed 99 modules. Its existing large-chunk warning is now
covered by the measured compressed-transfer budgets.

The backend gate passed 704 tests, Ruff lint, Ruff formatting, Pyright with zero errors or warnings,
and the locked dependency check. Six existing SQLAlchemy relationship warnings remain unchanged.

The fresh local stack applied the single Alembic head `e8a1c3f5b7d9` twice. The Phase 8D, 9B, 11C,
11D, 12F, and 12G database verifiers passed for all six protected file and output flows. Keycloak
configuration and its idempotence check passed before and after restart. The cross-role browser
journey and the 25-group accessibility journey passed.

The restart gate matched the database catalogue fingerprint and Keycloak signing-key identifiers.
The synthetic local attachment and private S3 object retained their expected bytes and scan state.
The token, database credential, generated password, and application identity-query log scans passed
before and after restart. The browser journey removed its synthetic rows and identities, and the
final database checks found none remaining.

The first local attempt used the repository-wide ESLint command, which included the broken ignored
Windows virtual environment and old files outside the Part 15F boundary. The corrected gate used the
workflow's changed-file lint. Two integration attempts then stopped at the Windows runner's missing
shell utilities; their `finally` blocks performed exact cleanup. The successful gate ran the same log
patterns and persistence SQL directly in PowerShell. No product, policy, denial, or budget rule was
changed to make a check pass.

## Performance record

The final `phase15f-local-loopback-chromium` profile used Chromium 148.0.7778.96, Node 24.11.1,
Windows x64, loopback networking, and no throttling. It measured 176,201 bytes for the compressed
initial transfer against 225,000, zero bytes for warm route changes against 1,024, and 172,563 bytes
for the largest compressed bundle against 210,000.

The 95th-percentile route change was 209 ms against 300 ms. Form feedback was 49.5 ms against 500
ms, and the representative `/health` API read was 6.89 ms against 500 ms. The evidence record includes
the profile, budgets, values, sample counts, percentile labels, and cache state.

## Catalogue and unchanged boundaries

Catalogue evidence now closes `P15-FIL-001` through `P15-FIL-006`, `P15-VAL-001` through
`P15-VAL-003`, `P15-FLOW-001` through `P15-FLOW-006`, `P15-GAP-005`, and golden cases
`15A-GC-025` through `15A-GC-030`. No later-part record changed. The Phase 15A contract still reports
52 inventory items, 31 client contracts, 29 routes, six file flows, eight owned gaps, 42 golden cases,
and seven later-part owners.

Part 15F added no backend endpoint, role, database schema, RLS policy, grant, protected function,
Keycloak claim, credential, generated business document, cloud resource, or business capability.
Alembic still has one recorded head at `e8a1c3f5b7d9`. No live or paid resource was accessed or
changed.

## Rollback and continuation

Part 15F rollback removes the acceptance verifier, route accessibility check, performance profile,
workflow steps, catalogue evidence, accessibility fixes, and this record. It restores the prior
Phase 3G browser selectors. It leaves the Phase 15B shell, the three role portals, backend contracts,
database, identity provider, protected storage, and cloud state unchanged.

After every routed GitHub job passes and the branch is clean and synchronized, Part 15G runs in a
new Codex task. It owns the Phase 15 documentation, operator runbook, rollback reconciliation,
independent review, and the final whole-phase owner signoff gate.
