# Phase 6G DigitalOcean infrastructure

This directory defines the temporary Phase 6G architecture proof. Provisioning is disabled by
default. The configuration does not create anything until `provisioning_authorized` is true and the
preflight confirmations pass.

## Fixed boundary

The proof uses these resources in Frankfurt:

- one free static App Platform component;
- one 1 vCPU, 1 GB FastAPI service at USD 10 per month;
- one 1 vCPU, 2 GB Keycloak service at USD 25 per month;
- one 1 vCPU, 1 GB managed PostgreSQL cluster at USD 15.15 per month;
- one private Space at USD 5 per month;
- one VPC and one short pre-deploy job.

The standing monthly rate is USD 55.15 before tax and overages. That monthly amount is not
authorized. The approved run is at most 48 hours, with an estimated prorated cost of USD 3.94. Stop
new work and request teardown approval if the team spend reaches USD 15. The absolute total ceiling
is USD 20. Do not resize components, add dedicated IPs, enable autoscaling, or add other billable
resources.

Current pricing references:

- <https://docs.digitalocean.com/products/app-platform/details/pricing/>
- <https://www.digitalocean.com/pricing/managed-databases>
- <https://docs.digitalocean.com/products/spaces/details/pricing/>

## Account preflight

Complete these checks before an authorized plan:

1. Confirm the USD 20 DigitalOcean spend alert is active. The alert is a notification, not a hard
   spending cap.
2. Confirm the DigitalOcean GitHub App can access only `AadhikR/workloop-clinic`.
3. Confirm the existing `workloop-clinic-dev` project contains no unrelated resources.
4. Confirm FRA1 already has a regional default VPC outside this proof. DigitalOcean automatically
   makes the first VPC in a region the default and does not allow that network to be deleted.
5. Create a short-lived DigitalOcean API token with only the project, app, database, VPC, Spaces-key,
   and project-assignment permissions needed by this configuration.
6. Create a temporary full-access Spaces key for Terraform to create and delete the private bucket.
   The app receives a separate bucket-scoped `readwrite` key. Revoke the temporary full-access key
   after teardown.
7. Choose a UTC teardown deadline no more than 48 hours after provisioning begins.
8. Generate two unrelated temporary passwords of at least 20 characters for the Keycloak bootstrap
   administrator and the synthetic login. Keep them out of files, shell history, chat, and source
   control.

## Sensitive local state

Terraform state contains database passwords and the bucket-scoped Spaces secret. Keep state outside
the repository in a user-only directory. Initialize the local backend with an explicit path, for
example:

```powershell
$phase6gState = Join-Path $env:LOCALAPPDATA 'Workloop\phase-6g\terraform.tfstate'
New-Item -ItemType Directory -Force (Split-Path $phase6gState) | Out-Null
terraform init -backend-config="path=$phase6gState"
```

Do not upload the state, plan file, token, key, or password. Retain the state until teardown is
verified because it is required to destroy the resources reliably.

## Safe deployment sequence

Copy `phase6g.tfvars.example` to an ignored `.auto.tfvars` file. Set the completed preflight flags,
the teardown deadline, and `provisioning_authorized = true`. Leave `public_exposure_enabled = false`
and `admin_mfa_gate_armed = false` for the first apply. Supply secrets through masked environment
prompts in a private terminal:

```powershell
$env:DIGITALOCEAN_TOKEN = Read-Host -MaskInput 'DigitalOcean API token'
$env:SPACES_ACCESS_KEY_ID = Read-Host -MaskInput 'Terraform Spaces access key'
$env:SPACES_SECRET_ACCESS_KEY = Read-Host -MaskInput 'Terraform Spaces secret key'
$env:TF_VAR_keycloak_bootstrap_admin_password = Read-Host -MaskInput 'Keycloak bootstrap password'
$env:TF_VAR_synthetic_user_password = Read-Host -MaskInput 'Synthetic login password'
```

Run `terraform plan -out phase6g.tfplan`, inspect the exact resource list and price sizes, then run
`terraform apply phase6g.tfplan`. The first deployment remains behind App Platform maintenance mode.
It is not the public proof.

In the App Platform console for the Keycloak component, run
`/opt/keycloak/bin/arm-admin-totp.sh`. The script targets the exact bootstrap administrator, sets
`CONFIGURE_TOTP` as its sole required action, removes both temporary kcadm configuration files, and
fails unless a fresh password-only login is refused. It does not print the password or a token.

After that control is verified, set `admin_mfa_gate_armed = true` and
`public_exposure_enabled = true`. Review and apply the second plan. Open the Keycloak admin console,
complete TOTP enrollment immediately, sign out, and prove that a new administrator login requires
both factors.

## Proof and teardown

The browser proof uses only `phase-6g-admin-test` and fixed synthetic database identifiers. Verify
login, current-account access, private object create/read/delete, exact issuer and callback values,
TLS, CORS, private database binding, and health. Redeploy the three components, then repeat the
identity, schema, and object checks to prove persistence.

Before teardown, capture resource sizes, estimated monthly cost, actual accrued spend, deployment
status, and persistence results without credentials or tokens. Teardown requires explicit owner
approval. Use the retained state for `terraform destroy`, confirm the project is empty, revoke the
temporary API and Spaces bootstrap keys, clear the five environment variables, and remove the local
state only after the destroy result is verified.

If DigitalOcean has made the proof VPC the regional default, the API will refuse to delete it even
after every member has been removed. Do not create a chain of replacement VPCs. Verify that the
network has zero members and the proof project is empty, then obtain explicit owner approval before
renaming the non-billable regional default and detaching only that VPC from Terraform state.
