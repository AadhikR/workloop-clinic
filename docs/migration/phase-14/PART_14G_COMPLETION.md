# Part 14G completion

## Result

Part 14G provisioned and promoted the approved DigitalOcean shared-development environment. The
environment contains synthetic data only, runs release `phase-14g-dc6e54a` at Alembic head
`e8a1c3f5b7d9`, and is available at the provider default address. The public web page and API health
endpoint both returned HTTP 200 after promotion.

The exact target remained within the owner's $15 time-boxed cap. Its reviewed run forecast is
$13.63, and manual cleanup is due by `2026-10-04T09:37:00+04:00`. Cleanup is not automatic.

## Release and live gate

The release binds commit `dc6e54afb4e16665a62b933999d85b83a57cb40a`, backend image digest
`sha256:e2bc596879407af3dcefadd8d0957950f4aadf67713f8252d4c5523a4e8bf11c`, the reviewed
Keycloak image, the frontend digest, and the single schema head. The release manifest and sanitized
live record are retained under `docs/migration/phase-14/evidence`.

The first apply stayed in maintenance mode with expiry, file scanning, and reconciliation disabled.
The live gate passed repeat migration, Keycloak MFA and bootstrap removal, secret routing, database
and object least privilege, component health, safe logging, provider-native backups, and isolated
point-in-time recovery. Restart and same-release redeploy checks preserved database state, Keycloak
signing-key IDs, private objects, both worker states, expiry state, and release identity.

The final synthetic gate resolved three Keycloak identities and passed the administrator, manager,
and employee authorization journeys. The public file flow passed. Expiry completed for one
synthetic clinic scope with no due insertions, and both retained workers reported processing-enabled
heartbeats.

## Controlled worker correction

The first worker-enablement deployment found an empty expiry scope and exited nonzero. Maintenance
never turned off. The operation immediately restored all three processing flags to false and
confirmed the rollback deployment was active.

The generated synthetic clinic already existed. The promotion helper was tightened to require its
company and branch UUIDs, bind that single scope, and refuse maintenance removal when the scope is
empty. The corrected worker deployment passed before traffic resumed. This was a fail-closed
configuration correction; it did not change the reviewed image or schema.

## Recovery, logs, and rollback

DigitalOcean retains daily automated database backups with seven-day point-in-time recovery. The
isolated restore matched both databases and was removed after comparison. The promoted log sweep
found no protected values. The API's four `unsafe_log_rejected` entries were expected INFO-level
logging-safety tests. Keycloak's two JGroups errors were graceful-close messages from replica
replacement. Neither represented a failed live check.

Runtime rollback first enables maintenance and stops every worker, then selects retained release
`phase-14g-ba12774`. It never downgrades the schema or deletes a resource.

## Verification

The complete local gate passed before publishing. The routed GitHub run passed every required job:
`https://github.com/AadhikR/workloop-clinic/actions/runs/36988853511`.

After that code gate, Part 14G added only release and completion evidence. The final Part 14G
contract verifier and changed-file checks cover those documentation-only additions; the passing
full-stack gate is not repeated.

## Preserved boundaries

The shared environment remains synthetic-only. No real employee, patient, payroll, banking, or
clinical record entered it. No custom domain, automatic deployment, Azure resource, Phase 13
archive, or unapproved provider resource entered the phase.

The protected local volume `workloop-clinic_postgres_data` was never attached, mounted, modified,
deleted, or recreated. Terraform state, plans, credentials, recovery material, and private console
payloads remain outside Git. Temporary console command files were removed after use.

## Next part

Part 14H independently traces every Phase 14 inventory item and golden case, repeats the closing
read-only live and synthetic checks, runs the complete phase gate, records Phase 14 completion, and
requests owner signoff. It must not start Phase 15.
