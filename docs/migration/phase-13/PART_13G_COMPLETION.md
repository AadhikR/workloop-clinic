# Part 13G boundary record

## Status

Part 13G remains blocked. Read-only discovery is complete, and the available provider snapshot is
encrypted outside Git. The isolated restore did not reproduce the current managed schemas, so the
retention period has not started. Part 13H must not start.

No API key, secret, bucket, object, project, or other external resource was changed or deleted.

## Read-only discovery

The authoritative Supabase organization is `otqemcwkpkyhpncmxldm`, and the project is
`lqnwmfhcogqaixgtcymc` in `ap-northeast-1`. The dashboard reported the project as active. Auth has
6 users and 6 identity records.

The database inventory contains 81 base tables and 951 rows. It records the public application RPC
names and the three observed views without storing record contents. The `supabase_realtime`
publication has no tables. Realtime is enabled, public channel access is allowed, and the current
pool, client, event, presence, and payload limits are recorded in the target manifest.

Storage has no buckets or objects. The API key inventory records only key classes, names, and safe
prefixes or suffixes for `web`, `mobile`, `backend_api`, `anon`, and `service_role`. It does not
record key values.

GitHub still has no environments or entries in the Actions, Agents, Codespaces, or Dependabot
repository secret stores. The authenticated DigitalOcean team has no App Platform applications, so
there are no application components or secret entries to target.

This resolves `P13-EXT-001` through `P13-EXT-008` without guessing identifiers or reading secret
values.

## Encrypted export

The encrypted artifacts are stored outside Git at
`C:\Users\aadhi\Documents\workloop-phase13g-retention`. The archive key is protected for the
current Windows user with DPAPI. AES-256-CBC with PBKDF2 and 600,000 iterations protects the two
artifacts.

The encrypted database artifact has SHA-256
`e906578379a8cf4e6a5a5c62c472b72c62175e5528111f7c912ca313fb01c95a`. The encrypted table-count
inventory has SHA-256
`5324c649624584b189dde40e7508ab871339451d7f94e6ebc267824e2ebbb81c`. A decryption round trip
reproduced both plaintext SHA-256 digests exactly.

The provider snapshot is dated 2026-09-12. It is preserved as evidence, but it is not current enough
to satisfy the restore gate against the 2026-09-27 discovery inventory.

After the decryption and restore checks, the two plaintext downloads and both temporary restore
directories were removed. They remain recoverable from the encrypted artifacts with the
current-user DPAPI key.

## Restore result

The restore ran in `postgres:17.6-bookworm` with memory-only database storage. It did not attach,
mount, modify, delete, or recreate `workloop-clinic_postgres_data`.

All 42 public application tables matched their live row counts. The restored Auth user and identity
counts also matched at 6 each. The strict comparison still failed with eight differences:

- four current empty Auth tables were absent from the snapshot;
- `auth.schema_migrations` restored 77 rows instead of 82;
- `realtime.schema_migrations` restored 82 rows instead of 86;
- `storage.migrations` restored 65 rows instead of 73; and
- `vault.secrets` was absent because the disposable image does not contain Supabase Vault.

The source had 81 tables and 951 rows. The isolated target had 76 tables and 934 rows. The target
manifest therefore records `restore.status` as `failed`, leaves both evidence bindings null, and
sets `countsAndDigestsMatch` to `false`.

The disposable restore container was removed after verification. The protected
`workloop-clinic_postgres_data` volume still exists.

## Retention and approval state

The failed restore prevents the retention clock from starting. The retention start and deadline are
null. The approval manifest remains `ineligible`, contains no approvals, and binds to this target
manifest.

The destructive target collections remain empty. `P13-RET-001`, `P13-RET-002`, `P13-DEL-001`,
`P13-DEL-002`, `P13-DEL-003`, `13A-GC-027`, `13A-GC-028`, and `13A-GC-030` remain open. The existing
denial verifier continues to reject failed restore, unexpired retention, broad targets, stale state,
and missing exact owner approval.

## Resume condition

Obtain a current export that reproduces the recorded live schema, row counts, Auth metadata counts,
and empty storage state in an isolated restore. A passing restore starts a new 30-calendar-day
retention period. After that deadline elapses, obtain fresh project-owner approval for each exact
target before any revocation or deletion.

Until those conditions pass, do not perform external destruction, claim Part 13G complete, or create
Part 13H.
