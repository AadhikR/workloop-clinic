# Part 13A dependency inventory

## Scope and method

This inventory covers all 1,097 files tracked at commit
`2323475ae93e0a4e76055285488f20bac1cb5775`. The scan found 260 tracked files with a
case-insensitive `Supabase` marker. The tracked 15-page HRMS feature-list PDF is binary and therefore
outside that text count. Text extraction and a complete page render found Supabase Auth, Edge
Function, RPC, and Storage instructions in it. Its digest covers the canonical indexed Git blob, not
platform-normalized working-tree bytes. The focused verifier reads the current tracked-file set on every
run. It assigns each marker-bearing file to exactly one coverage group and counts every other file
as inspected and reference-free. A new marker-bearing file fails until its group and dependency are
declared.

The machine-readable source is `docs/migration/phase-13/dependency-catalogue.json`. The tables below
must match its ID, item, disposition, and owner fields exactly. The only allowed dispositions are:

- `remove`
- `replace`
- `retain as inert negative proof`
- `retain as labeled history`
- `inspect externally`
- `destroy only after exact owner approval`

Each item has one owner from 13B through 13G. Part 13H reviews the result but owns no change.

## Repository findings

The root `src` tree has 96 tracked files. Fourteen files either create or import the Supabase client,
and six more contain Supabase-specific user text or supporting behavior. The migration `src` tree has
75 tracked files. Its build rejects Supabase and legacy-source imports, and its source files contain
no Supabase runtime reference.

The root package declares `@supabase/supabase-js` as a development dependency. The lockfile adds
`@supabase/auth-js`, `@supabase/functions-js`, `@supabase/phoenix`,
`@supabase/postgrest-js`, `@supabase/realtime-js`, and `@supabase/storage-js`. Realtime has no direct
application call. It remains in the install graph through the client package.

The active legacy configuration reads `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY`.
`.env.test.example` also names `SUPABASE_SERVICE_ROLE_KEY` and contains a credential-shaped public
key example tied to a repository candidate project reference. This file is evidence, not authority
for current external state. No repository file proves which of those names exists in a GitHub or
DigitalOcean secret store.

The default `dev`, `build`, and `preview` commands still select the legacy app. The migration app uses
explicit commands, port 5174, and `dist-migration`. CI runs the default build, while the DigitalOcean
static component runs the migration build and consumes `dist-migration`. Compose has no frontend
service and no Supabase setting. It still supplies the backend and Keycloak runtime that browser
proof depends on.

The root `supabase*.sql` files and `sql/` directory do not participate in the current Alembic or local
database bootstrap path. They are legacy source-system SQL. Two Alembic revisions retain the word
only to explain source semantics. Part 13E must label and isolate those records without rewriting
the append-only migration chain. Alembic has one head at `e8a1c3f5b7d9`; Part 13A changes no schema
file.

## Build and promotion dependencies

| ID | Item | Disposition | Owner |
| --- | --- | --- | --- |
| `P13-BLD-001` | Default npm dev, build, and preview commands | `replace` | 13B |
| `P13-BLD-002` | Explicit migration dev and build commands | `replace` | 13B |
| `P13-BLD-003` | Legacy and migration entry points, ports, and output paths | `replace` | 13B |
| `P13-BLD-004` | CI and DigitalOcean frontend build inputs | `replace` | 13B |
| `P13-BLD-005` | Compose and backend frontend-origin inputs | `replace` | 13B |
| `P13-BLD-006` | Migration public environment allowlist | `replace` | 13B |

Part 13B makes the migration app the default without moving source trees. Ordinary commands, CI,
deployment inputs, the fixed browser origin, and the consumed output must change together. A
temporary legacy rollback command may remain only by an explicit name.

## Source and service dependencies

| ID | Item | Disposition | Owner |
| --- | --- | --- | --- |
| `P13-SRC-001` | Seventy-five-file migration frontend source graph | `replace` | 13C |
| `P13-SRC-002` | Ninety-six-file legacy frontend source graph | `remove` | 13C |
| `P13-SRC-003` | Dual-build isolation controls | `remove` | 13C |
| `P13-SRC-004` | Legacy freeze tests tied to removed source | `remove` | 13C |
| `P13-SRC-005` | Six Phase 12 dependencies retained for Phase 13 | `remove` | 13C |
| `P13-SVC-001` | Supabase Auth client calls and auth-state listener | `remove` | 13C |
| `P13-SVC-002` | Supabase table and PostgREST calls | `remove` | 13C |
| `P13-SVC-003` | Eight direct Supabase RPC call targets | `remove` | 13C |
| `P13-SVC-004` | Supabase Realtime runtime class with no direct application call | `remove` | 13D |
| `P13-SVC-005` | Supabase Storage client calls for two buckets | `remove` | 13C |

The Auth methods are `getSession`, `onAuthStateChange`, `resetPasswordForEmail`,
`signInWithPassword`, `signOut`, and `signUp`. The legacy source has direct table targets for
attendance, organization, employee, leave, payroll, expense, notification, task, document,
insurance, appraisal, certification, offboarding, roster, and shift-swap data. The authoritative
call-level list remains in `docs/migration/phase-0/SUPABASE_DEPENDENCY_INVENTORY.md` until Part 13E
labels it as history.

The eight direct RPC targets are:

- `employee_submit_regularisation`
- `employee_submit_document`
- `employee_cancel_leave_request`
- `employee_submit_leave_request`
- `employee_update_contact`
- `link_employee_account`
- `manager_get_expense_queue`
- `manager_get_leave_queue`

The Storage bucket names present in source and historical contracts are `employee-documents` and
`expense-receipts`. Repository inspection proves no Postgres Realtime `.channel()` or `.subscribe()`
call. It does not prove that the external project has no Realtime configuration.

The six Phase 12 entries assigned to Phase 13 are `P12-NOT-14`, `P12-TSK-17`, `P12-DSH-12`,
`P12-RPT-19`, `P12-OUT-18`, and `P12-IND-08`. Part 13C closes them when it removes the frozen legacy
consumers and generators.

## Package and environment dependencies

| ID | Item | Disposition | Owner |
| --- | --- | --- | --- |
| `P13-PKG-001` | Direct @supabase/supabase-js development dependency | `remove` | 13D |
| `P13-PKG-002` | Six transitive Supabase packages | `remove` | 13D |
| `P13-ENV-001` | VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY inputs | `remove` | 13D |
| `P13-ENV-002` | SUPABASE_SERVICE_ROLE_KEY test input | `remove` | 13D |
| `P13-ENV-003` | Checked-in Supabase URL and credential-shaped examples | `remove` | 13D |

Part 13D removes the direct package and verifies that all six transitive packages leave the lockfile
and clean install. It also removes the three environment names from active examples, source,
allowlists, tests that no longer need them, CI, Compose, infrastructure, and deployment input.
Negative tests may use unmistakably inert values under Part 13E's allowlist. They may not reuse the
repository candidate project reference or a token-shaped value.

## History, tests, and guardrails

| ID | Item | Disposition | Owner |
| --- | --- | --- | --- |
| `P13-HIS-001` | Root and sql directory legacy Supabase SQL | `retain as labeled history` | 13E |
| `P13-HIS-002` | Backend migration and test references to source-system semantics | `retain as labeled history` | 13E |
| `P13-HIS-003` | Phase 0 through Phase 12 migration records | `retain as labeled history` | 13E |
| `P13-DOC-001` | Current setup, architecture, roadmap, checklist, and contributor documents | `replace` | 13E |
| `P13-DOC-002` | Phase 13 current contract and evidence documents | `retain as labeled history` | 13E |
| `P13-DOC-003` | Legacy feature-list generator | `replace` | 13E |
| `P13-DOC-004` | Generated HRMS feature-list PDF with Supabase instructions | `retain as labeled history` | 13E |
| `P13-TST-001` | Frontend negative tests and sentinels containing Supabase names | `retain as inert negative proof` | 13E |
| `P13-TST-002` | Verifier sentinels and historical assertions containing Supabase names | `retain as inert negative proof` | 13E |
| `P13-GRD-001` | Repository guard for active references and labeled exceptions | `replace` | 13E |
| `P13-DB-001` | Portable Alembic schema at head e8a1c3f5b7d9 | `retain as inert negative proof` | 13E |

Current documents are `README.md`, `ARCHITECTURE.md`, `CLAUDE.md`, `FEATURES_ROADMAP.md`,
`MANUAL_TEST_CHECKLIST.md`, `REMAINING_TESTS.md`, and `backend/README.md`. The generated
`Workloop_Clinic_HRMS_Feature_List.pdf` is a historical roadmap, not a current implementation
instruction. Part 13E must label it accordingly. Part 13E must remove
current setup instructions that describe Supabase as active. Earlier migration records stay
readable and immutable apart from a clear historical label or relocation that preserves Git
history.

An inert negative proof names a forbidden package, environment key, host, service, or operation only
inside a fixture or assertion. It cannot be imported by production code, accepted as runtime
configuration, included in a built artifact, or used as a network destination. Part 13E replaces
the temporary 13A coverage contract with the permanent repository guard.

## Clean setup and no-network dependencies

| ID | Item | Disposition | Owner |
| --- | --- | --- | --- |
| `P13-NET-001` | Clean locked install and production module graph scan | `replace` | 13F |
| `P13-NET-002` | Supabase DNS lookup attempts | `retain as inert negative proof` | 13F |
| `P13-NET-003` | Supabase HTTP, WebSocket, PostgreSQL, and object-storage attempts | `retain as inert negative proof` | 13F |
| `P13-NET-004` | Fresh disposable full-stack setup without Supabase values | `replace` | 13F |

Part 13F must detect attempted traffic, not only successful traffic. A failed DNS lookup, refused TCP
connection, rejected TLS handshake, or blocked HTTP response still fails. The proof covers the
frontend, browser, backend, tools, workers, test helpers, and dependency install output. Package
registry access during the locked install is allowed, but installed package names and tarball URLs
must contain no `@supabase` package after 13D.

The full-stack proof uses named disposable resources and synthetic data. It must never attach,
modify, delete, or recreate `workloop-clinic_postgres_data`.

## External discovery, retention, and destruction

| ID | Item | Disposition | Owner |
| --- | --- | --- | --- |
| `P13-EXT-001` | External Supabase project identity and status | `inspect externally` | 13G |
| `P13-EXT-002` | External Supabase Auth users and metadata | `inspect externally` | 13G |
| `P13-EXT-003` | External Supabase database tables and RPC objects | `inspect externally` | 13G |
| `P13-EXT-004` | External employee-documents and expense-receipts buckets | `inspect externally` | 13G |
| `P13-EXT-005` | External Supabase Realtime configuration | `inspect externally` | 13G |
| `P13-EXT-006` | External Supabase API keys and key identifiers | `inspect externally` | 13G |
| `P13-EXT-007` | GitHub Supabase secret and environment names | `inspect externally` | 13G |
| `P13-EXT-008` | DigitalOcean Supabase secret and environment names | `inspect externally` | 13G |
| `P13-DEL-001` | Approved Supabase keys and secret-store entries | `destroy only after exact owner approval` | 13G |
| `P13-DEL-002` | Approved Supabase buckets and objects | `destroy only after exact owner approval` | 13G |
| `P13-DEL-003` | Approved external Supabase project | `destroy only after exact owner approval` | 13G |
| `P13-RET-001` | Encrypted export and isolated restore evidence | `inspect externally` | 13G |
| `P13-RET-002` | Thirty-day minimum retention deadline | `inspect externally` | 13G |
| `P13-APR-001` | Denial of unapproved destructive actions | `retain as inert negative proof` | 13G |

The only repository candidate project reference is `lqnwmfhcogqaixgtcymc`. Part 13G must not treat it
as authoritative. Read-only discovery must resolve the exact project, organization, GitHub
repository and environment, DigitalOcean app and component, secret entry names, key identifiers,
Auth counts, database objects, Realtime state, bucket names, object counts, sizes, and hashes.
Credential values, private objects, exports, and personal data stay out of Git and task messages.

The candidate secret names are `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`, and
`SUPABASE_SERVICE_ROLE_KEY`. A candidate is not a deletion target. Missing access or a name mismatch
stops the destructive portion of 13G.

## Coverage groups

The machine catalogue partitions every tracked marker-bearing file into these non-overlapping
groups: legacy source, package graph, active environment, dual-build control, legacy freeze tests,
test negative proof, script negative proof, historical SQL, backend history, migration history,
Phase 13 current records, current documentation, and the feature-list generator. The verifier fails
on zero or multiple matches.

Files without the marker still matter. The inventory accounts for the whole migration source graph,
default commands, build outputs, CI, Compose, infrastructure, backend origin, public environment
allowlist, and the Alembic head through explicit catalogue entries. The reference-free rule does not
claim that a file is safe forever. Part 13E's permanent guard and Part 13F's module and network proof
must test the settled repository again.

## Decision record

The retention minimum is 30 calendar days after a successful isolated restore. The owner may extend
that deadline but cannot shorten it. This is the smallest local rule that preserves a recovery window
without claiming a legal retention period that the repository does not define.

No external object is eligible for deletion merely because Phase 13 started or because repository
proof passed. Eligibility requires a resolved exact target, complete encrypted export evidence,
successful restore evidence, an elapsed retention deadline, and fresh owner approval naming that
target. If any condition is absent, 13G records the manifest and stops.
