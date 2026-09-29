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
  -var='reviewed_monthly_forecast_usd=65.15' \
  -var='reviewed_run_forecast_usd=15.01' \
  >"$validation_directory/forecast-rejected.log" 2>&1; then
  printf '%s\n' 'A reviewed forecast above USD 15 did not block new work.' >&2
  exit 1
fi
if ! grep -q 'temporary-run forecast at or below the USD 15 owner cap' "$validation_directory/forecast-rejected.log"; then
  cat "$validation_directory/forecast-rejected.log" >&2
  exit 1
fi

printf '%s\n' 'Phase 14E disabled Terraform and USD 15 owner-cap guards passed.'
