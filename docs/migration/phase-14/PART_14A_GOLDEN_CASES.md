# Part 14A golden cases

## Use

These cases are fixed acceptance inputs for Parts 14B through 14H. The machine copies live in
`docs/migration/phase-14/deployment-catalogue.json`. A later part may add a narrower case, but it
must not weaken, renumber, reassign, or silently drop one of these cases.

## Cases

| ID | Owner | Area | Expected result |
| --- | --- | --- | --- |
| `14A-GC-001` | 14B | disabled apply | An unapproved plan creates no resource, state, credential, or public route. |
| `14A-GC-002` | 14B | names | Project, app, cluster, databases, bucket, components, region, and VPC match exactly. |
| `14A-GC-003` | 14B | network | Terraform reads `fra1-default` by exact identity, creates no replacement, and binds privately. |
| `14A-GC-004` | 14B | storage | The private bucket rejects public access, enables versioning, and cannot force deletion. |
| `14A-GC-005` | 14B | address | Custom domains, wildcard CORS, and wildcard callbacks fail validation. |
| `14A-GC-006` | 14B | cost | Fixed sizes total USD 65.15, the architecture ceiling stays USD 70, and a stricter owner cap remains enforceable. |
| `14A-GC-007` | 14C | database roles | Six login roles remain separate and cross-role operations are denied. |
| `14A-GC-008` | 14C | object keys | API, scanner, reconciler, and backup processes receive only declared bucket actions. |
| `14A-GC-009` | 14C | frontend secrets | No protected value reaches the React build or emitted bytes. |
| `14A-GC-010` | 14C | bootstrap | Bootstrap access is removed after MFA, and fresh password-only administrator login fails. |
| `14A-GC-011` | 14C | rotation | Rotation records owner, overlap, verification, revocation, and rollback without values. |
| `14A-GC-012` | 14C | operator access | Missing solo-operator, MFA, emergency-access, recovery-custody, or separate-review evidence blocks provisioning. |
| `14A-GC-013` | 14D | artifacts | One manifest binds commit, image, frontend, lock, Terraform, app spec, and schema digests. |
| `14A-GC-014` | 14D | migration | Migration reaches `e8a1c3f5b7d9`, repeats as a no-op, and blocks incompatible services. |
| `14A-GC-015` | 14D | health | All seven components satisfy their exact health or completion rule. |
| `14A-GC-016` | 14D | scanner concurrency | One scanner claims one row with the fixed lease, attempts, and retry schedule. |
| `14A-GC-017` | 14D | reconciler concurrency | One reconciler recovers stale leases without duplicate object mutation. |
| `14A-GC-018` | 14D | expiry concurrency | Two runs for the same scope and date produce one result through the advisory lock. |
| `14A-GC-019` | 14D | shutdown | A worker stops new claims and finishes or releases the current lease before termination. |
| `14A-GC-020` | 14D | automatic deployment | A branch push or mutable tag cannot deploy any component automatically. |
| `14A-GC-021` | 14E | safe logs | Logs and evidence contain no protected value, signed URL, or document content. |
| `14A-GC-022` | 14E | alerts | Every signal has one owner, severity, threshold, response, retention, and test method. |
| `14A-GC-023` | 14E | worker monitoring | Stale heartbeat, queue age, expired lease, retry, and terminal failure emit safe signals. |
| `14A-GC-024` | 14E | cost response | A forecast or plan above the stricter USD 15 owner cap blocks work, and an alert never claims to cap spending. |
| `14A-GC-025` | 14E | incident | Maintenance, notification, evidence, rollback, and recovery record times and operators. |
| `14A-GC-026` | 14F | database restore | Both databases restore in isolation with matching schema, identity, rows, and signing keys. |
| `14A-GC-027` | 14F | object restore | Object restore reproduces version, key, count, byte, and digest manifests privately. |
| `14A-GC-028` | 14F | write block | Restored writes and workers stay disabled until every recovery check passes. |
| `14A-GC-029` | 14F | rollback | Rollback uses the prior schema-compatible manifest and never downgrades automatically. |
| `14A-GC-030` | 14F | cleanup | Cleanup deletes only named recovery targets after sanitized evidence is retained. |
| `14A-GC-031` | 14G | preflight | Fresh discovery resolves account, target, prices, alerts, access, owners, and custody. |
| `14A-GC-032` | 14G | approval | Phase authorization cannot approve a paid apply. The exact manifest needs dated approval. |
| `14A-GC-033` | 14G | maintenance | First apply and incompatible updates stay in maintenance until promotion passes. |
| `14A-GC-034` | 14G | persistence | Restart and redeploy preserve data, keys, objects, worker state, and release identity. |
| `14A-GC-035` | 14G | retention | The 72-hour deadline enables maintenance and stops workers without automatic deletion. |
| `14A-GC-036` | 14H | trace | Every inventory and case ID appears once with no owner gap or overlap. |
| `14A-GC-037` | 14H | boundary | No real data, custom domain, external delivery, Azure work, archive change, or unapproved resource enters. |
| `14A-GC-038` | 14H | rollback order | Phase rollback follows 14H through 14A without deleting preserved resources. |

## Fixed fixtures

Infrastructure tests use a disabled plan, the exact names in the operations contract, and hostile
values for custom domains, wildcard routes, public bucket settings, forced deletion, autoscaling,
mutable artifacts, and excess cost. Every hostile case fails before a resource operation.

Role tests use one synthetic identity per database and object permission. Cross-role reads, writes,
claims, migrations, object operations, and administrator actions fail. No fixture contains a real
credential.

Recovery tests use separate application, Keycloak, object, release, and configuration manifests.
Approval for one target does not approve another. Restore targets remain isolated and writes stay
disabled until the full recovery order passes.
