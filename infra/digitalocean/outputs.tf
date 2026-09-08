output "app_url" {
  description = "Default App Platform URL for the temporary proof."
  value       = local.enabled ? digitalocean_app.proof[0].default_ingress : null
}

output "app_id" {
  description = "App identifier used for verification and teardown."
  value       = local.enabled ? digitalocean_app.proof[0].id : null
}

output "database_cluster_id" {
  description = "Managed PostgreSQL identifier used for verification and teardown."
  value       = local.enabled ? digitalocean_database_cluster.proof[0].id : null
}

output "spaces_bucket_name" {
  description = "Private synthetic-object bucket used by the proof."
  value       = local.enabled ? digitalocean_spaces_bucket.proof[0].name : null
}

output "estimated_monthly_usd" {
  description = "Full-month rate if the temporary proof is left running."
  value       = local.estimated_monthly_usd
}

output "estimated_test_window_usd" {
  description = "Prorated estimate for the approved test window before tax and overages."
  value       = format("%.2f", local.estimated_test_window_usd)
}

output "teardown_deadline_utc" {
  description = "Owner-approved UTC deadline for destroying the temporary resources."
  value       = var.teardown_deadline_utc
}
