# Part 13G retention and external disposition completion

## Status

Part 13G is complete. The correct Supabase project has a current encrypted export and a passing
isolated restore. On 2026-09-27, the project owner chose to retain that project indefinitely instead
of deleting it. No key, secret, bucket, object, project, or other external resource was revoked,
changed, or deleted.

The minimum retention period started at `2026-09-27T09:06:58Z` and would have ended at
`2026-10-27T09:06:58Z`. Indefinite retention extends that minimum without shortening it. The
approval manifest contains no destructive approvals, and the verifier denies every settled target.

## Corrected project identity

The authoritative Supabase organization is `otqemcwkpkyhpncmxldm`. The Workloop project is
`workloop-clinic`, project ref `dabphibgpamsfoxfhwmu`, in `ap-southeast-1`. The dashboard reported
the project as healthy.

An earlier read-only discovery used `AadhikR's Project`, ref `lqnwmfhcogqaixgtcymc`. That project was
not changed. Its counts, export, and failed restore did not describe Workloop, so this record replaces
them. The older encrypted artifacts remain outside Git and are excluded from every Workloop target
and approval.

## Read-only discovery

The correct project has 6 Auth users and 6 identity records. Its database has 91 base tables and
1,005 rows. The manifest records all table counts, 29 public RPC names, one overloaded RPC name,
three views, and an empty `supabase_realtime` publication without storing row contents.

Realtime is enabled, public channel access is allowed, and the recorded limits match the dashboard.
The database and Postgres Changes pools both have size 2. The project allows 200 concurrent clients,
100 events per second, 20 presence events per second, and 256 KB payloads.

Storage has two buckets. `employee-documents` has 6 objects and 2,043,166 bytes.
`expense-receipts` is empty. The manifest stores a SHA-256 digest of each bucket's ordered object
name and provider ETag metadata. It does not store object names, object contents, or download private
files.

The API key inventory records only four safe identifiers. GitHub still has no repository
environments or entries in the Actions, Agents, Codespaces, or Dependabot secret stores. The
authenticated DigitalOcean team still has no App Platform applications.

## Encrypted export

The verified artifacts are stored outside Git at
`C:\Users\aadhi\Documents\workloop-phase13g-retention\workloop-clinic-dabphibgpamsfoxfhwmu-2026-09-27`.
The archive key is protected for the current Windows user with DPAPI. AES-256-CBC with
PBKDF2-SHA256 and 600,000 iterations protects the database and count artifacts.

The encrypted database artifact has SHA-256
`f1c7fd94d7144203422e95e8e59e505021ca11134df8331f69df336d03bd3b66`. Its plaintext database
digest is `bda3cd8dad2142e473cd04dfb0d323abc93bebb6421569f23d105507962797ce`.

The encrypted count artifact has SHA-256
`8430b0561257f40f2727e68f9d9779c8c2f4898de4ff8e270a5c34d126aaabc5`. Its plaintext digest is
`7b24fc21a7b5dfbf0bebbe8054dd0f2de7926d42126c6afbb511ac84b60dd2b8`.

A decryption round trip reproduced both plaintext digests. The DPAPI key blob has SHA-256
`ad943142a347618306b1faf045736153ca67856d878ab547f4184a2263ec7919`.

## Isolated restore

The first disposable restore attempt used plain PostgreSQL 17.6. It stopped before data comparison
because that image does not contain the Supabase Vault extension. The container was removed.

The successful restore used the official `supabase/postgres:17.6.1.136` image with digest
`sha256:f371b5f3f2ac0a05703f33d6e6134515fb2498cab708fb948a0aeb7481467c00`. Its database storage
used container memory only. It did not attach, mount, modify, delete, or recreate
`workloop-clinic_postgres_data`.

The source and restore both contain 91 tables and 1,005 rows. All public application counts, Auth
counts, RPC signatures, views, publication membership, storage counts, byte totals, and storage
metadata digests match. The normalized comparison digest is
`3b257f851063f542c4c272ee5cd5b795a22c3a59700c539ae6ae6d6e0f1b5267`. The manifest evidence
digest is `c0a68fa0b54b5a5507eb4c387bced3d743f525689f563f947f1c100c59072d16` for both sides.

## Cleanup and settled disposition

The disposable restore container, plaintext dump, plaintext count inventory, temporary directory,
and five temporary helper files were removed. The encrypted artifacts remain. The protected Docker
volume `workloop-clinic_postgres_data` remains present and unchanged.

The owner decision closes `P13-RET-002`, `P13-DEL-001`, `P13-DEL-002`, and `P13-DEL-003` by changing
their disposition from planned destruction to external retention. All Part 13G dependencies and
golden cases now pass. The retained project is archive-only and has no active application,
configuration, package, credential, or network dependency in the Workloop runtime.

Part 13H may start. Its independent review must treat the Supabase project, its keys, its Auth data,
its database, and both storage buckets as preserved resources. Any future deletion is outside Phase
13 and requires a new scope amendment, a fresh read-only manifest, and fresh exact owner approvals.
