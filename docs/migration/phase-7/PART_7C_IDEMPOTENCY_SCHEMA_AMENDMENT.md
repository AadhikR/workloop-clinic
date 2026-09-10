# Phase 7C idempotency cleanup amendment

## Status

The project owner approved decision `7C-IDEM-D2` on 2026-09-10. The rest of approved decision
`7C-IDEM-D1` remains unchanged.

## Finding

Implementation review found a conflict between two requirements in `7C-IDEM-D1`:

- runtime `SELECT` must expose only the current user's idempotency records; and
- any active principal may delete up to 100 expired records for the current company without reading
  another user's record.

PostgreSQL applies the `SELECT` policy to the subquery that identifies rows for a limited, ordered
`DELETE`. The approved query can therefore locate only the caller's records. The broader `DELETE`
policy does not change that visibility rule.

Caller-only cleanup is safe, but it is incomplete. A disabled user cannot return to clean expired
records. Those records can then keep the restrictive profile and company foreign keys alive after
the seven-day retention floor.

## Proposed amendment

Add `public.cleanup_expired_idempotency_records()` with no arguments. It returns the number of rows
deleted as an integer.

The function has these properties:

- `LANGUAGE plpgsql`, `VOLATILE`, and `SECURITY DEFINER`;
- ownership by `workloop_migration`;
- `search_path` fixed to `pg_catalog, public, pg_temp`;
- execute revoked from `PUBLIC` and granted only to `workloop_runtime`;
- no company, user, timestamp, or limit argument;
- validation that `session_user` is `workloop_runtime` and that the transaction contains the trusted
  human context for a currently resolved active principal;
- company scope derived only from `public.workloop_company_id()`;
- deletion of at most 100 completed rows whose `retain_until` is not later than
  `statement_timestamp()`;
- row selection ordered by `retain_until`, `created_at`, `app_user_id`, and `idempotency_key`; and
- an integer result from 0 through 100, with no record contents or identifiers returned.

The function owner already has the migration policy on the forced-RLS table. The function therefore
locates expired rows across the verified company while its caller remains unable to select another
user's record.

Revoke direct table `DELETE` from `workloop_runtime`. Runtime keeps table `SELECT` and `INSERT`, plus
the existing column-level completion `UPDATE` grant. The delete policy remains as defense in depth,
but runtime cleanup goes only through the function.

`IdempotencyRepository.cleanup_expired()` calls the function and rejects a result outside 0 through
100. Claim and status transactions continue to invoke one bounded cleanup pass before looking up the
current key.

The Alembic downgrade revokes runtime execute, drops the function, and then performs the already
approved idempotency downgrade. The protected-function catalogue verifier adds the new signature.

## Required proof

Focused migration and RLS checks must prove all of the following:

- one active user can remove an expired record owned by another user in the same company;
- the function cannot remove an unexpired record;
- cleanup cannot cross companies;
- one call deletes no more than 100 rows in the specified order;
- inactive, invalid, and non-runtime contexts cannot call the function successfully;
- runtime cannot delete directly from the table; and
- the function returns no idempotency record contents.

## Decision request

Approve `7C-IDEM-D2` to add the bounded cleanup function, its runtime execute grant, the direct
`DELETE` revocation, the protected-function catalogue entry, downgrade handling, and the focused
proof above. This amendment changes no request fingerprint, replay rule, retention duration,
business mutation, audit action, or later-phase authority.
