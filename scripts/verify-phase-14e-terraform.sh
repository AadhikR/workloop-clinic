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
  -var='reviewed_monthly_forecast_usd=70.01' \
  >"$validation_directory/forecast-rejected.log" 2>&1; then
  printf '%s\n' 'A reviewed forecast above USD 70 did not block new work.' >&2
  exit 1
fi
if ! grep -q 'reviewed monthly forecast exceeds USD' "$validation_directory/forecast-rejected.log"; then
  cat "$validation_directory/forecast-rejected.log" >&2
  exit 1
fi

printf '%s\n' 'Phase 14E disabled Terraform and USD 70 forecast guards passed.'
