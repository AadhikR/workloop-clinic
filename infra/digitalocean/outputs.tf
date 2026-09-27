output "app_url" {
  description = "Provider-managed App Platform address, or null while provisioning is disabled."
  value       = local.enabled ? digitalocean_app.shared[0].default_ingress : null
}

output "app_id" {
  description = "Shared-development app identifier, or null while provisioning is disabled."
  value       = local.enabled ? digitalocean_app.shared[0].id : null
}

output "database_cluster_id" {
  description = "Managed PostgreSQL identifier, or null while provisioning is disabled."
  value       = local.enabled ? digitalocean_database_cluster.shared[0].id : null
}

output "spaces_bucket_name" {
  description = "Exact private bucket name, or null while provisioning is disabled."
  value       = local.enabled ? local.spaces_bucket_name : null
}

output "estimated_monthly_usd" {
  description = "Fixed monthly estimate, or null while provisioning is disabled."
  value       = local.enabled ? local.estimated_monthly_usd : null
}

output "configuration_ceiling_usd" {
  description = "Maximum fixed monthly configuration cost, or null while provisioning is disabled."
  value       = local.enabled ? local.configuration_ceiling_usd : null
}

output "provisioning_enabled" {
  description = "True only for an enabled plan. It is absent from disabled state."
  value       = local.enabled ? true : null
}

output "database_identity_names" {
  description = "Database identity names, or null while provisioning is disabled."
  value = local.enabled ? [
    digitalocean_database_user.workloop_migration[0].name,
    digitalocean_database_user.workloop_runtime[0].name,
    digitalocean_database_user.workloop_expiry_processing[0].name,
    digitalocean_database_user.workloop_file_scanner[0].name,
    digitalocean_database_user.workloop_storage_reconciler[0].name,
    digitalocean_database_user.keycloak[0].name,
  ] : null
}

output "object_identity_names" {
  description = "Object identity names, or null while provisioning is disabled."
  value = local.enabled ? [
    digitalocean_spaces_key.api[0].name,
    digitalocean_spaces_key.file_scanner[0].name,
    digitalocean_spaces_key.storage_reconciler[0].name,
    digitalocean_spaces_key.object_backup[0].name,
  ] : null
}

output "operator_access_ready" {
  description = "True only when every operator role has distinct named MFA accounts."
  value       = local.enabled ? local.operator_access_complete : null
}

output "release_identity" {
  description = "Safe immutable release identity, or null while provisioning is disabled."
  value = local.enabled ? {
    release_id            = var.release_manifest.release_id
    git_commit            = var.release_manifest.git_commit
    backend_image_digest  = var.release_manifest.backend_image.digest
    keycloak_image_digest = var.release_manifest.keycloak_image.digest
    frontend_sha256       = var.release_manifest.frontend_sha256
    alembic_head          = var.release_manifest.alembic_head
  } : null
}
