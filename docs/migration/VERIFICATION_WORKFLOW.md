# Migration verification workflow

This document defines the default verification and source-control flow for every migration phase and
task. The goal is to preserve strong evidence while avoiding checks that repeat proof already obtained
for unchanged code.

## Select checks from the change

Classify the task before implementation:

| Change class | Required checks |
| --- | --- |
| Documentation only | Formatting and changed-file validation only |
| Backend only | Backend tests, lint, formatting, types, and dependency checks |
| Frontend only | Frontend unit tests and the production build |
| Database, migration, RLS, grants, or database infrastructure | Backend and frontend checks, full-stack smoke, and deep database checks |
| Authentication, Keycloak, Compose, or shared infrastructure | Backend and frontend checks, full-stack smoke, and affected authentication checks |
| Unknown or workflow-control files | Treat as full-stack sensitive |

The GitHub workflow applies this classification from changed paths. A manual workflow run always uses
the complete gate.

## Development loop

1. Perform a read-only preflight and identify the affected boundary.
2. Add or update the focused verifier before the implementation becomes broad.
3. Implement one bounded change.
4. Run only the checks that give fast evidence for that change.
5. Fix failures with the smallest relevant check.
6. Repeat until the phase code is stable.

Do not run the full stack after every edit. Do not repeat frontend, browser, migration-history, or
authentication checks when the changed files cannot affect those boundaries.

## Phase completion gate

Run one complete local gate in a fresh isolated environment after the phase code is stable. The gate
must cover each boundary changed by the phase and any rollback or restart proof required by the phase
plan. If it fails, diagnose with focused checks, fix the cause, and rerun the complete gate once after
the fix.

The complete gate should:

- install or build each changed runtime once;
- apply the migration twice to prove repeatability;
- run historical downgrade and upgrade chains only for database-sensitive changes;
- run deep schema, RLS, grant, function, and concurrency checks only for database-sensitive changes;
- configure authentication once, with a second configuration pass only when authentication setup
  changed and idempotence is under test;
- record database and signing-key state before a restart;
- restart the existing images without rebuilding them;
- compare persisted state and verify authentication after restart without reconfiguring it; and
- clean synthetic data and temporary resources.

Do not rerun the same migration build outside the unit suite when the unit suite already performs it.
Do not use a table count as a second schema verifier. Do not rerun the full historical verifier set
after restart when a deterministic persisted-state comparison proves that the catalog is unchanged.

## Commit and push

Prefer one local commit per independently reviewable migration or domain. Run the final local gate
once after all phase code is stable, then push the phase once and wait for the required GitHub result.

After the phase code has passed its complete local and GitHub gates, later documentation-only edits do
not invalidate that code evidence. Commit and push those edits with only the lightweight changed-file
validation. Do not trigger another full-stack run merely to publish a completion note, workflow URL,
handoff prompt, or process document.

If code changes after the passing phase gate, classify the new changes normally and rerun the affected
checks. If the changed code crosses a database, authentication, Compose, or shared infrastructure
boundary, run the complete gate again.

## Evidence to report

At task completion, report:

- the commit and branch;
- the focused checks run during implementation;
- the final local gate, when required;
- the GitHub result required for that change class; and
- any preserved volume, service, or resource that remains intentionally unchanged.

Do not create another commit only to store a successful workflow URL unless the phase plan requires
it. Put that URL in the task handoff or completion report.
