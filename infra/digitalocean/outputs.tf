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
