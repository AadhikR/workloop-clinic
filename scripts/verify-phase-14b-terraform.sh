#!/bin/sh
set -eu

source_directory=${1:-/source}
validation_directory=$(mktemp -d)
trap 'rm -rf "$validation_directory"' EXIT

cp "$source_directory"/*.tf "$validation_directory"/
cp "$source_directory/.terraform.lock.hcl" "$validation_directory"/
mkdir -p "$validation_directory/.terraform"
cp -R "$source_directory/.terraform/providers" "$validation_directory/.terraform/"

terraform -chdir="$validation_directory" fmt -check -diff
terraform -chdir="$validation_directory" init \
  -backend-config="path=$validation_directory/terraform.tfstate" \
  -input=false
terraform -chdir="$validation_directory" validate
terraform -chdir="$validation_directory" plan \
  -detailed-exitcode \
  -refresh=false \
  -input=false \
  -lock=false \
  -out="$validation_directory/disabled.tfplan"

if terraform -chdir="$validation_directory" plan \
  -refresh=false \
  -input=false \
  -lock=false \
  -var='provisioning_authorized=true' \
  >"$validation_directory/rejected.log" 2>&1; then
  printf '%s\n' 'An enabled plan without approval inputs did not fail.' >&2
  exit 1
fi
grep -q 'requires every field in the reviewed Phase 14 target approval' "$validation_directory/rejected.log"

cat >"$validation_directory/approved-without-operators.tfvars" <<'EOF'
provisioning_authorized = true
approval = {
  target_manifest_id       = "synthetic-test-only"
  owner_approval_reference = "synthetic-test-only"
  approved_on              = "2026-09-27"
  price_reviewed_on        = "2026-09-27"
  retention_review_due_on  = "2026-10-27"
  state_custodian          = "synthetic-test-only"
  state_path_reference     = "synthetic-test-only"
  credential_custodian     = "synthetic-test-only"
  infrastructure_owner     = "synthetic-test-only"
  security_owner           = "synthetic-test-only"
  application_owner        = "synthetic-test-only"
  incident_owner           = "synthetic-test-only"
  release_reviewer         = "synthetic-test-only"
  backup_custodian         = "synthetic-test-only"
  variable_charge_owner    = "synthetic-test-only"
  cleanup_manifest_id      = "synthetic-test-only"
}
EOF

if terraform -chdir="$validation_directory" plan \
  -refresh=false \
  -input=false \
  -lock=false \
  -var-file="$validation_directory/approved-without-operators.tfvars" \
  >"$validation_directory/operator-rejected.log" 2>&1; then
  printf '%s\n' 'An enabled plan without operator records did not fail.' >&2
  exit 1
fi
grep -q 'Provisioning requires one named solo operator' "$validation_directory/operator-rejected.log"
grep -q 'requires the complete encrypted runtime-secret input' "$validation_directory/operator-rejected.log"

cat >>"$validation_directory/approved-without-operators.tfvars" <<'EOF'
operator_access = {
  operator_name = "synthetic-solo-operator"
  routine_account_reference = "synthetic-routine-account"
  routine_mfa = true
  emergency_account_reference = "synthetic-emergency-account"
  emergency_mfa = true
  recovery_material_custody_reference = "synthetic-offline-recovery-location"
  recovery_tested_on = "2026-09-27"
  roles = [
    "infrastructure_custodian",
    "security_custodian",
    "application_operator",
    "incident_operator",
    "release_reviewer",
  ]
  separate_review_record = true
}
runtime_secrets = {
  api_storage_signing_key = "synthetic"
  api_attachment_object_key_hmac_key = "synthetic"
  api_cursor_signing_key = "synthetic"
  api_idempotency_current_key_id = "synthetic"
  api_idempotency_current_key = "synthetic"
  api_idempotency_previous_keys = "[]"
  scanner_malware_signing_key = "synthetic"
}
EOF

if terraform -chdir="$validation_directory" plan \
  -refresh=false \
  -input=false \
  -lock=false \
  -var-file="$validation_directory/approved-without-operators.tfvars" \
  >"$validation_directory/manifest-rejected.log" 2>&1; then
  printf '%s\n' 'An enabled plan without a release manifest did not fail.' >&2
  exit 1
fi
grep -q 'requires one complete deployable release manifest' "$validation_directory/manifest-rejected.log"

printf '%s\n' 'Phase 14B disabled Terraform plan contains no changes.'
