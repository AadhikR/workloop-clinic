# Part 13G boundary record

## Status

Part 13G is blocked at the approved external-access boundary. It is not complete, its catalogue
closure is absent, and Part 13H must not start.

The repository now has a read-only target manifest, an approval manifest that is explicitly
ineligible, a pure approval verifier, and denial fixtures. No key, secret, bucket, object, project,
or other external resource was changed.

## Read-only discovery

GitHub discovery used the signed-in repository settings for `AadhikR/workloop-clinic`. The
repository has no environments. Its Actions, Agents, Codespaces, and Dependabot repository secret
stores contain no entries. This resolves `P13-EXT-007` without guessing candidate names or reading
values.

The available sessions were not signed in to the external project provider or DigitalOcean. No
provider command-line client or matching credential variable was available. The repository's
historical candidate identifiers were not promoted to authoritative targets. `P13-EXT-001` through
`P13-EXT-006` and `P13-EXT-008` remain unresolved.

## Retention and approval state

No source access meant no encrypted export or isolated restore could run. The target manifest keeps
the export and restore states at `not-started`. It records no external location, custodian, digest,
count, or private content. The retention start and deadline remain null, so the thirty-day period
has not begun.

The target manifest contains no destructive targets. The approval manifest binds to the exact
target-manifest digest but remains `ineligible` with an empty approval list. There are no action
receipts because no action occurred.

The focused verifier accepts a destructive action only when every discovery section is resolved,
the encrypted export matches the discovery evidence, the isolated restore reproduces that evidence,
the retention deadline is at least thirty calendar days after restore and has elapsed, and one fresh
project-owner approval issued after that deadline matches one exact settled target. A read-only
preflight must then match the target within fifteen minutes of the action check. The verifier denies
phase authorization, wildcards, partial targets, stale approval, changed or stale preflight state,
failed restore, unexpired retention, and uncertain owner identity.

This design closes `P13-APR-001` and proves golden cases `13A-GC-024`, `13A-GC-026`,
`13A-GC-029`, `13A-GC-031` through `13A-GC-033`, and `13A-GC-036`. The remaining Part 13G entries
and cases stay open in the catalogue boundary record.

## Repository and data boundaries

The verifier has no external client, command runner, network call, deletion path, or project
creation path. The Part 13E exact-path guard is unchanged. Alembic remains at one head,
`e8a1c3f5b7d9`.

`workloop-clinic_postgres_data` remains protected. Part 13G did not attach, mount, modify, delete,
or recreate it. No production record, private object, export, credential, key value, or personal
data entered Git or task output.

## Resume condition

Resume Part 13G only after authenticated read-only access is available for the authoritative
external project and DigitalOcean application. Discovery must settle exact identifiers, counts, and
digests before export and restore. A successful restore starts the retention period. After the full
deadline elapses, the project owner must approve each exact target against the settled manifest.

Until all of those conditions pass, do not perform external destruction, claim Part 13G complete,
or create Part 13H.
