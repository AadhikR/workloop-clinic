# Part 14G provisioning and promotion runbook

## Scope

This runbook controls the synthetic shared-development deployment. It does not approve a paid
resource. Keep every committed example disabled. Store the exact manifest, credentials, Terraform
state, plans, backups, and restricted evidence outside Git under the named custodians.

The target is limited to the existing `workloop-clinic-dev` project and `fra1-default` VPC. Never
attach, mount, modify, delete, or recreate `workloop-clinic_postgres_data`. Do not change the Phase
13 external archive. Do not create a custom domain, delivery service, Azure resource, or real data.

## Fresh preflight

Repeat the authenticated preflight no more than 30 minutes before an enabled plan or apply. Record
the account, project ID, VPC ID and CIDR, every current resource, product availability, current
prices, spend and forecast, budget alert, GitHub branch and commit, required Actions result, and the
DigitalOcean GitHub App repository scope. Stop if the App can access more than
`AadhikR/workloop-clinic`, any target name belongs to another resource, or any fact is unresolved.

Record the named solo operator once and assign all five role hats. Record an MFA-protected
least-privilege routine account, a distinct MFA-protected emergency account, the safe custody
reference for offline recovery material, and the last successful recovery-test date. Execution and
review use separate records even though the same person performs both. Record the state,
credential, backup, and variable-charge custodians by safe reference; they may all name the same
operator. Do not put credentials, MFA seeds, recovery material, tokens, passwords, connection
strings, keys, or private state paths in repository evidence.

For the private manifest, complete the solo-operator fields as follows:

| Field | What to record |
| --- | --- |
| `operatorName` | Your real name. |
| `routineAccountReference` | A safe reference to your normal least-privilege provider account, not its credential. |
| `routineMfa` | `true` only after you have completed an MFA sign-in. |
| `emergencyAccountReference` | A safe reference to a distinct recovery account or emergency access path that you control and do not use routinely. |
| `emergencyMfa` | `true` only after you have tested MFA on that emergency path. |
| `recoveryMaterialCustodyReference` | A safe label for the offline encrypted location holding recovery material; never the material itself. |
| `recoveryTestedOn` | The `YYYY-MM-DD` date when you last proved the recovery path works. |
| `roleHats` | Keep the five fixed role names. They describe which responsibility you were performing, not five people. |
| `separateReviewRecord` | Keep `true`; record execution first and review it in a separate dated entry before promotion. |

The four custody fields are also references, not extra people. `stateCustodian` identifies who and
where the encrypted Terraform state is held. `credentialCustodian` does the same for passwords and
keys. `backupCustodian` points to the encrypted backup location and recovery responsibility.
`variableChargeOwner` identifies who reviews metered charges and stops work before the USD 15 cap.
For a solo project, all four may name you, but each must point to the correct protected record or
storage location.

Create the private target manifest from `phase-14g-target-manifest.example.json`. Replace its
repository commit with the clean reviewed commit and attach the deployable release manifest. Run
`scripts/phase-14g-control.mjs validate-target` before asking for approval. Ask the owner to approve
the resulting SHA-256 digest, monthly reference cost, 72-hour maximum, temporary-run forecast,
variable-charge ownership, exposure order, and exact manual cleanup boundary. Any edit after
approval changes the digest and
voids that approval.

The owner set a USD 15 total-usage cap on 2026-09-28 and selected manual cleanup. The unchanged
architecture costs USD 65.15 for a full billing month. Using the provider's 672-hour App Platform
billing month as the conservative basis, 72 hours projects to USD 6.99 before tax and variable
usage. The private manifest must include a reviewed total-run forecast between USD 6.99 and USD 15,
an exact start time, and a cleanup deadline no more than 72 hours later. This is a planning guard,
not a provider-enforced spending cap. Billing may lag, and no cleanup runs automatically.

## Maintenance-first provisioning

Run `authorize-apply` against the private manifest immediately before work begins. An error stops
the window. Use short-lived provider access and the approved encrypted state location. Create one
saved plan for the exact manifest. Review its resource names, sizes, regions, instance counts,
private network, private versioned bucket, fixed cost, maintenance setting, and destruction actions.
The plan must contain no deletion and no resource outside the manifest.

Apply only that saved plan. The first deployment stays in maintenance, and expiry, scanner, and
reconciler processing stays disabled. Record the safe project, VPC, app, database, and bucket
identifiers. Run the migration twice and prove the only head is `e8a1c3f5b7d9`.

Create the permanent Keycloak administrator, enroll MFA, and use
`keycloak/cloud/arm-admin-totp.sh` to remove bootstrap access. Remove the bootstrap settings and
redeploy Keycloak. A fresh password-only bootstrap login must fail, and the permanent administrator
must receive an MFA challenge. A failed check leaves maintenance on.

## Live gate

Verify every database role and object key through allowed and denied operations. Check that each
secret reaches only its owning component and that the web build receives only its six public
settings. Prove API, Keycloak, web, migration, expiry, scanner, and reconciler health or completion.
Scan safe logs for protected values.

Record the provider-native backup schedule and retention for both databases. Restore the required
point in time into isolated targets and run the Part 14F comparisons. Do not restore over the shared
environment. The `pending-14g-provider-live` dependency stays blocked until this proof passes.

Run the complete synthetic administrator, manager, and employee journeys while maintenance remains
on. Record database state, Keycloak signing-key IDs, private-object counts and digests, scanner,
reconciler, expiry, and release identities. Restart the existing deployment without a rebuild and
compare each item. Then redeploy the same digest-bound release and compare them again.

## Promotion

Fill a private live record from `phase-14g-live-record.example.json` and retain a sanitized copy in
Git only after every live check passes. The promotion approval must bind the release manifest digest,
resource IDs, current cost, backup result, rollback point, and next review date. Run
`authorize-promotion` before changing the final state.

Enable worker processing first. Disable maintenance only after worker heartbeats, authentication,
authorization, private files, and reconciliation pass again. Provider deployment success by itself
does not approve promotion.

## Temporary run and manual cleanup

Keep the app, database, and bucket only for the owner-directed test window. The owner decides when
cleanup begins and must give fresh approval for the exact targets. The run must not be approved for
more than 72 hours. At the deadline, the helper's fixed state is maintenance on, workers off, no
automatic cleanup, and owner action required. Do not represent that state as a hard spending stop.
Before and after each test session, review accrued usage and the forecast because provider billing
can lag.

## Rollback and cleanup

Enable maintenance and stop expiry, scanner, and reconciler claims. Select only the exact retained
compatible release recorded in the live evidence. Keep the schema at `e8a1c3f5b7d9`; never run an
automatic downgrade. Preserve databases, private objects, logs, state, backups, and incident
evidence. Redeploy the reviewed digests and repeat health, authentication, authorization, object,
worker, and reconciliation checks before traffic resumes.

Runtime rollback does not delete a resource. When the owner directs cleanup, obtain fresh approval
for the exact app, database, bucket, credentials, alerts, retained state, and backup disposition.
Empty and delete the private bucket so its Spaces subscription ends, then verify that the app,
database cluster, bucket, scoped credentials, and temporary alerts are absent. The project, default
VPC, Phase 13 archive, and protected local volume are never cleanup targets.
