locals {
  app_region            = "fra"
  resource_region       = "fra1"
  project_name          = "workloop-clinic-dev"
  project_id            = "634213f9-2e43-4aea-8f4e-22ddc3ecdac9"
  app_name              = "workloop-clinic-dev"
  database_cluster_name = "workloop-clinic-dev-db"
  spaces_bucket_name    = "workloop-clinic-dev-634213f9"
  vpc_name              = "fra1-default"
  vpc_id                = "b8b6d17b-eae4-47de-b2b5-9d10baabdd2d"
  vpc_cidr              = "10.114.0.0/20"
  github_repository     = "AadhikR/workloop-clinic"
  github_branch         = "migration/fastapi-keycloak"
  expected_alembic_head = "e8a1c3f5b7d9"

  ownership_labels = {
    environment = "shared-development"
    data_class  = "synthetic-only"
    managed_by  = "terraform"
    owner_role  = "infrastructure-custodian"
  }
  ownership_tags = [for key, value in local.ownership_labels : "${key}:${value}"]

  fixed_monthly_costs = {
    api                = 10
    keycloak           = 25
    file_scanner       = 5
    storage_reconciler = 5
    managed_postgresql = 15.15
    spaces_standard    = 5
    web_static_site    = 0
  }
  estimated_monthly_usd     = sum(values(local.fixed_monthly_costs))
  configuration_ceiling_usd = 70
  owner_usage_cap_usd       = var.owner_usage_cap_usd
  billing_month_hours       = 672
  projected_base_usage_usd  = 6.99

  approval_complete = var.approval != null && alltrue([
    for value in [
      try(var.approval.target_manifest_id, ""),
      try(var.approval.owner_approval_reference, ""),
      try(var.approval.approved_on, ""),
      try(var.approval.price_reviewed_on, ""),
      try(var.approval.retention_review_due_on, ""),
      try(var.approval.state_custodian, ""),
      try(var.approval.state_path_reference, ""),
      try(var.approval.credential_custodian, ""),
      try(var.approval.infrastructure_owner, ""),
      try(var.approval.security_owner, ""),
      try(var.approval.application_owner, ""),
      try(var.approval.incident_owner, ""),
      try(var.approval.release_reviewer, ""),
      try(var.approval.backup_custodian, ""),
      try(var.approval.variable_charge_owner, ""),
      try(var.approval.cleanup_manifest_id, ""),
    ] : length(trimspace(value)) > 0
  ])

  operator_access_complete = var.operator_access != null && try(
    length(trimspace(var.operator_access.operator_name)) > 0 &&
    length(trimspace(var.operator_access.routine_account_reference)) > 0 &&
    var.operator_access.routine_mfa &&
    length(trimspace(var.operator_access.emergency_account_reference)) > 0 &&
    var.operator_access.emergency_mfa &&
    var.operator_access.routine_account_reference != var.operator_access.emergency_account_reference &&
    length(trimspace(var.operator_access.recovery_material_custody_reference)) > 0 &&
    can(regex("^[0-9]{4}-[0-9]{2}-[0-9]{2}$", var.operator_access.recovery_tested_on)) &&
    var.operator_access.separate_review_record &&
    var.operator_access.roles == toset([
      "infrastructure_custodian",
      "security_custodian",
      "application_operator",
      "incident_operator",
      "release_reviewer",
    ]),
    false,
  )

  runtime_secrets_complete = nonsensitive(var.runtime_secrets != null && alltrue([
    for value in [
      try(var.runtime_secrets.api_storage_signing_key, ""),
      try(var.runtime_secrets.api_attachment_object_key_hmac_key, ""),
      try(var.runtime_secrets.api_cursor_signing_key, ""),
      try(var.runtime_secrets.api_idempotency_current_key_id, ""),
      try(var.runtime_secrets.api_idempotency_current_key, ""),
      try(var.runtime_secrets.api_idempotency_previous_keys, ""),
      try(var.runtime_secrets.scanner_malware_signing_key, ""),
    ] : length(trimspace(value)) > 0
  ]))

  release_manifest_complete = var.release_manifest != null && try(
    var.release_manifest.deployable &&
    can(regex("^[a-z0-9][a-z0-9._-]{2,79}$", var.release_manifest.release_id)) &&
    can(regex("^[0-9a-f]{40}$", var.release_manifest.git_commit)) &&
    alltrue([
      for value in [
        var.release_manifest.backend_image.registry_type,
        var.release_manifest.backend_image.repository,
        var.release_manifest.keycloak_image.registry_type,
        var.release_manifest.keycloak_image.repository,
      ] : length(trimspace(value)) > 0
    ]) &&
    contains(["DOCR", "DOCKER_HUB"], var.release_manifest.backend_image.registry_type) &&
    contains(["DOCR", "DOCKER_HUB"], var.release_manifest.keycloak_image.registry_type) &&
    (var.release_manifest.backend_image.registry_type == "DOCR" ?
      var.release_manifest.backend_image.registry == "" :
    length(trimspace(var.release_manifest.backend_image.registry)) > 0) &&
    (var.release_manifest.keycloak_image.registry_type == "DOCR" ?
      var.release_manifest.keycloak_image.registry == "" :
    length(trimspace(var.release_manifest.keycloak_image.registry)) > 0) &&
    alltrue([
      for value in [
        var.release_manifest.backend_image.digest,
        var.release_manifest.keycloak_image.digest,
        var.release_manifest.frontend_sha256,
        var.release_manifest.frontend_root_sha256,
        var.release_manifest.dependency_lock_sha256.frontend,
        var.release_manifest.dependency_lock_sha256.backend,
        var.release_manifest.dependency_lock_sha256.backend_dev,
        var.release_manifest.terraform_sha256,
        var.release_manifest.app_spec_sha256,
      ] : can(regex("^sha256:[0-9a-f]{64}$", value))
    ]),
    false,
  )
  release_manifest_compatible = local.release_manifest_complete && try(
    var.release_manifest.alembic_head == local.expected_alembic_head &&
    var.release_manifest.release_id == var.approval.target_manifest_id,
    false,
  )
  worker_processing_enabled = var.release_promoted && var.release_promotion_approved && local.release_manifest_compatible
  expiry_processing_enabled = local.worker_processing_enabled && length(var.expiry_scopes) > 0
  access_boundary_complete  = var.provisioning_authorized && local.approval_complete && local.operator_access_complete && local.runtime_secrets_complete

  enabled = (
    local.access_boundary_complete &&
    local.release_manifest_complete
  )
}

data "digitalocean_project" "shared" {
  count = local.enabled ? 1 : 0
  name  = local.project_name
}

data "digitalocean_vpc" "default" {
  count = local.enabled ? 1 : 0
  id    = local.vpc_id
}

resource "terraform_data" "phase_14_guard" {
  count = local.enabled ? 1 : 0
  input = {
    app_name                 = local.app_name
    database_cluster_name    = local.database_cluster_name
    estimated_monthly_usd    = local.estimated_monthly_usd
    projected_base_usage_usd = local.projected_base_usage_usd
    maximum_runtime_hours    = var.maximum_runtime_hours
    spaces_bucket_name       = local.spaces_bucket_name
  }

  lifecycle {
    precondition {
      condition     = !var.provisioning_authorized || local.approval_complete
      error_message = "Provisioning requires every field in the reviewed Phase 14 target approval."
    }
    precondition {
      condition     = !var.provisioning_authorized || local.operator_access_complete
      error_message = "Provisioning requires one named solo operator, MFA-protected routine and emergency accounts, tested recovery custody, all five operator roles, and a separate review record."
    }
    precondition {
      condition     = !var.provisioning_authorized || local.runtime_secrets_complete
      error_message = "Provisioning requires the complete encrypted runtime-secret input."
    }
    precondition {
      condition     = !var.provisioning_authorized || local.release_manifest_complete
      error_message = "Provisioning requires one complete deployable release manifest with immutable artifact digests."
    }
    precondition {
      condition     = !var.provisioning_authorized || local.release_manifest_compatible
      error_message = "The release manifest must match the approved target and Alembic head before compatible services can activate."
    }
    precondition {
      condition = try(
        local.projected_base_usage_usd <= local.owner_usage_cap_usd &&
        var.reviewed_run_forecast_usd != null &&
        var.reviewed_run_forecast_usd >= local.projected_base_usage_usd &&
        var.reviewed_run_forecast_usd <= local.owner_usage_cap_usd,
        false,
      )
      error_message = "The temporary-run forecast must cover projected base usage and stay at or below the owner's USD 15 total-usage cap."
    }
    precondition {
      condition     = data.digitalocean_project.shared[0].id == local.project_id
      error_message = "The project name does not resolve to the verified workloop-clinic-dev project ID."
    }
    precondition {
      condition = (
        data.digitalocean_vpc.default[0].id == local.vpc_id &&
        data.digitalocean_vpc.default[0].name == local.vpc_name &&
        data.digitalocean_vpc.default[0].region == local.resource_region &&
        data.digitalocean_vpc.default[0].ip_range == local.vpc_cidr &&
        data.digitalocean_vpc.default[0].default
      )
      error_message = "The verified fra1-default VPC identity changed. Stop before plan and do not create or import a replacement."
    }
    precondition {
      condition = (
        var.configuration_ceiling_usd == local.configuration_ceiling_usd &&
        local.estimated_monthly_usd <= var.configuration_ceiling_usd
      )
      error_message = "The fixed monthly configuration must stay at USD 65.15 and at or below the USD 70 ceiling."
    }
    precondition {
      condition     = !var.release_promoted || (var.release_promotion_approved && local.release_manifest_compatible)
      error_message = "The provider default address must stay in maintenance mode without a recorded release promotion approval."
    }
    precondition {
      condition     = !var.release_promoted || length(var.expiry_scopes) > 0
      error_message = "Release promotion requires at least one approved synthetic expiry scope."
    }
  }
}

resource "digitalocean_database_cluster" "shared" {
  count                = local.enabled ? 1 : 0
  name                 = local.database_cluster_name
  engine               = "pg"
  version              = "16"
  size                 = "db-s-1vcpu-1gb"
  region               = local.resource_region
  node_count           = 1
  storage_size_mib     = "10240"
  private_network_uuid = data.digitalocean_vpc.default[0].id
  tags                 = local.ownership_tags

  maintenance_window {
    day  = "sunday"
    hour = "03:00:00"
  }

  depends_on = [terraform_data.phase_14_guard]
}

resource "digitalocean_database_db" "workloop" {
  count      = local.enabled ? 1 : 0
  cluster_id = digitalocean_database_cluster.shared[0].id
  name       = "workloop"
}

resource "digitalocean_database_db" "keycloak" {
  count      = local.enabled ? 1 : 0
  cluster_id = digitalocean_database_cluster.shared[0].id
  name       = "keycloak"
}

resource "digitalocean_database_user" "workloop_migration" {
  count      = local.enabled ? 1 : 0
  cluster_id = digitalocean_database_cluster.shared[0].id
  name       = "workloop_migration"

  lifecycle {
    ignore_changes = [settings]
  }
}

resource "digitalocean_database_user" "workloop_runtime" {
  count      = local.enabled ? 1 : 0
  cluster_id = digitalocean_database_cluster.shared[0].id
  name       = "workloop_runtime"

  lifecycle {
    ignore_changes = [settings]
  }
}

resource "digitalocean_database_user" "workloop_expiry_processing" {
  count      = local.enabled ? 1 : 0
  cluster_id = digitalocean_database_cluster.shared[0].id
  name       = "workloop_expiry_processing"

  lifecycle {
    ignore_changes = [settings]
  }
}

resource "digitalocean_database_user" "workloop_file_scanner" {
  count      = local.enabled ? 1 : 0
  cluster_id = digitalocean_database_cluster.shared[0].id
  name       = "workloop_file_scanner"

  lifecycle {
    ignore_changes = [settings]
  }
}

resource "digitalocean_database_user" "workloop_storage_reconciler" {
  count      = local.enabled ? 1 : 0
  cluster_id = digitalocean_database_cluster.shared[0].id
  name       = "workloop_storage_reconciler"

  lifecycle {
    ignore_changes = [settings]
  }
}

resource "digitalocean_database_user" "keycloak" {
  count      = local.enabled ? 1 : 0
  cluster_id = digitalocean_database_cluster.shared[0].id
  name       = "keycloak"

  lifecycle {
    ignore_changes = [settings]
  }
}

resource "digitalocean_spaces_bucket" "shared" {
  count         = local.enabled ? 1 : 0
  name          = local.spaces_bucket_name
  region        = local.resource_region
  acl           = "private"
  force_destroy = false

  versioning {
    enabled = true
  }

  lifecycle {
    prevent_destroy = true
  }

  depends_on = [terraform_data.phase_14_guard]
}

resource "digitalocean_spaces_key" "api" {
  count = local.enabled ? 1 : 0
  name  = "workloop-clinic-dev-api"

  grant {
    bucket     = digitalocean_spaces_bucket.shared[0].name
    permission = "readwrite"
  }
}

resource "digitalocean_spaces_key" "file_scanner" {
  count = local.enabled ? 1 : 0
  name  = "workloop-clinic-dev-file-scanner"

  grant {
    bucket     = digitalocean_spaces_bucket.shared[0].name
    permission = "read"
  }
}

resource "digitalocean_spaces_key" "storage_reconciler" {
  count = local.enabled ? 1 : 0
  name  = "workloop-clinic-dev-storage-reconciler"

  grant {
    bucket     = digitalocean_spaces_bucket.shared[0].name
    permission = "readwrite"
  }
}

resource "digitalocean_spaces_key" "object_backup" {
  count = local.enabled ? 1 : 0
  name  = "workloop-clinic-dev-object-backup"

  grant {
    bucket     = digitalocean_spaces_bucket.shared[0].name
    permission = "read"
  }
}

resource "digitalocean_app" "shared" {
  count = local.enabled ? 1 : 0

  spec {
    name   = local.app_name
    region = local.app_region

    maintenance {
      enabled = !var.release_promoted
    }

    env {
      key   = "WORKLOOP_ENVIRONMENT"
      value = local.ownership_labels.environment
      scope = "RUN_AND_BUILD_TIME"
      type  = "GENERAL"
    }

    env {
      key   = "WORKLOOP_DATA_CLASS"
      value = local.ownership_labels.data_class
      scope = "RUN_AND_BUILD_TIME"
      type  = "GENERAL"
    }

    env {
      key   = "WORKLOOP_INFRASTRUCTURE_OWNER"
      value = local.ownership_labels.owner_role
      scope = "RUN_AND_BUILD_TIME"
      type  = "GENERAL"
    }

    env {
      key   = "WORKLOOP_RELEASE_ID"
      value = try(var.release_manifest.release_id, "")
      scope = "RUN_AND_BUILD_TIME"
      type  = "GENERAL"
    }

    env {
      key   = "WORKLOOP_RELEASE_COMMIT"
      value = try(var.release_manifest.git_commit, "")
      scope = "RUN_AND_BUILD_TIME"
      type  = "GENERAL"
    }

    env {
      key   = "WORKLOOP_ALEMBIC_HEAD"
      value = try(var.release_manifest.alembic_head, "")
      scope = "RUN_TIME"
      type  = "GENERAL"
    }

    alert {
      rule = "DEPLOYMENT_FAILED"
    }

    alert {
      rule = "DOMAIN_FAILED"
    }

    vpc {
      id = data.digitalocean_vpc.default[0].id
    }

    database {
      name         = "workloop-admin"
      engine       = "PG"
      production   = true
      cluster_name = digitalocean_database_cluster.shared[0].name
      db_name      = digitalocean_database_db.workloop[0].name
      db_user      = digitalocean_database_cluster.shared[0].user
    }

    database {
      name         = "keycloak-admin"
      engine       = "PG"
      production   = true
      cluster_name = digitalocean_database_cluster.shared[0].name
      db_name      = digitalocean_database_db.keycloak[0].name
      db_user      = digitalocean_database_cluster.shared[0].user
    }

    database {
      name         = "workloop-migration"
      engine       = "PG"
      production   = true
      cluster_name = digitalocean_database_cluster.shared[0].name
      db_name      = digitalocean_database_db.workloop[0].name
      db_user      = digitalocean_database_user.workloop_migration[0].name
    }

    database {
      name         = "workloop-runtime"
      engine       = "PG"
      production   = true
      cluster_name = digitalocean_database_cluster.shared[0].name
      db_name      = digitalocean_database_db.workloop[0].name
      db_user      = digitalocean_database_user.workloop_runtime[0].name
    }

    database {
      name         = "workloop-expiry"
      engine       = "PG"
      production   = true
      cluster_name = digitalocean_database_cluster.shared[0].name
      db_name      = digitalocean_database_db.workloop[0].name
      db_user      = digitalocean_database_user.workloop_expiry_processing[0].name
    }

    database {
      name         = "workloop-file-scanner"
      engine       = "PG"
      production   = true
      cluster_name = digitalocean_database_cluster.shared[0].name
      db_name      = digitalocean_database_db.workloop[0].name
      db_user      = digitalocean_database_user.workloop_file_scanner[0].name
    }

    database {
      name         = "workloop-storage-reconciler"
      engine       = "PG"
      production   = true
      cluster_name = digitalocean_database_cluster.shared[0].name
      db_name      = digitalocean_database_db.workloop[0].name
      db_user      = digitalocean_database_user.workloop_storage_reconciler[0].name
    }

    database {
      name         = "keycloak-runtime"
      engine       = "PG"
      production   = true
      cluster_name = digitalocean_database_cluster.shared[0].name
      db_name      = digitalocean_database_db.keycloak[0].name
      db_user      = digitalocean_database_user.keycloak[0].name
    }

    job {
      name               = "database-migrate"
      kind               = "PRE_DEPLOY"
      instance_count     = 1
      instance_size_slug = "apps-s-1vcpu-1gb-fixed"
      run_command        = "python -m app.db.cloud_migrate"

      image {
        registry_type = try(var.release_manifest.backend_image.registry_type, "DOCR")
        registry      = try(var.release_manifest.backend_image.registry, "invalid")
        repository    = try(var.release_manifest.backend_image.repository, "invalid")
        digest        = var.release_manifest.backend_image.digest
      }

      env {
        key   = "CLOUD_ADMIN_WORKLOOP_DATABASE_URL"
        value = "$${workloop-admin.DATABASE_PRIVATE_URL}"
        scope = "RUN_TIME"
        type  = "SECRET"
      }

      env {
        key   = "CLOUD_ADMIN_KEYCLOAK_DATABASE_URL"
        value = "$${keycloak-admin.DATABASE_PRIVATE_URL}"
        scope = "RUN_TIME"
        type  = "SECRET"
      }

      env {
        key   = "MIGRATION_DATABASE_URL"
        value = "$${workloop-migration.DATABASE_PRIVATE_URL}"
        scope = "RUN_TIME"
        type  = "SECRET"
      }

      env {
        key   = "WORKLOOP_PUBLIC_URL"
        value = "$${APP_URL}"
        scope = "RUN_TIME"
        type  = "GENERAL"
      }

      env {
        key   = "WORKLOOP_ALEMBIC_HEAD"
        value = try(var.release_manifest.alembic_head, "")
        scope = "RUN_TIME"
        type  = "GENERAL"
      }
    }

    service {
      name               = "api"
      instance_count     = 1
      instance_size_slug = "apps-s-1vcpu-1gb-fixed"
      http_port          = 8000

      image {
        registry_type = try(var.release_manifest.backend_image.registry_type, "DOCR")
        registry      = try(var.release_manifest.backend_image.registry, "invalid")
        repository    = try(var.release_manifest.backend_image.repository, "invalid")
        digest        = var.release_manifest.backend_image.digest
      }

      env {
        key   = "APP_ENV"
        value = "development"
        scope = "RUN_TIME"
        type  = "GENERAL"
      }

      env {
        key   = "APP_BASE_URL"
        value = "$${APP_URL}"
        scope = "RUN_TIME"
        type  = "GENERAL"
      }

      env {
        key   = "FRONTEND_URL"
        value = "$${APP_URL}"
        scope = "RUN_TIME"
        type  = "GENERAL"
      }

      env {
        key   = "DATABASE_URL"
        value = "$${workloop-runtime.DATABASE_PRIVATE_URL}"
        scope = "RUN_TIME"
        type  = "SECRET"
      }

      env {
        key   = "OIDC_ISSUER"
        value = "$${APP_URL}/auth/realms/workloop-dev"
        scope = "RUN_TIME"
        type  = "GENERAL"
      }

      env {
        key   = "OIDC_AUDIENCE"
        value = "workloop-api"
        scope = "RUN_TIME"
        type  = "GENERAL"
      }

      env {
        key   = "OIDC_JWKS_URL"
        value = "$${APP_URL}/auth/realms/workloop-dev/protocol/openid-connect/certs"
        scope = "RUN_TIME"
        type  = "GENERAL"
      }

      env {
        key   = "TRUSTED_PROXY"
        value = "digitalocean_app_platform"
        scope = "RUN_TIME"
        type  = "GENERAL"
      }

      env {
        key   = "STORAGE_BACKEND"
        value = "spaces"
        scope = "RUN_TIME"
        type  = "GENERAL"
      }

      env {
        key   = "SPACES_ENDPOINT_URL"
        value = "https://${local.resource_region}.digitaloceanspaces.com"
        scope = "RUN_TIME"
        type  = "GENERAL"
      }

      env {
        key   = "SPACES_REGION"
        value = local.resource_region
        scope = "RUN_TIME"
        type  = "GENERAL"
      }

      env {
        key   = "SPACES_BUCKET"
        value = digitalocean_spaces_bucket.shared[0].name
        scope = "RUN_TIME"
        type  = "GENERAL"
      }

      env {
        key   = "SPACES_ACCESS_KEY"
        value = digitalocean_spaces_key.api[0].access_key
        scope = "RUN_TIME"
        type  = "SECRET"
      }

      env {
        key   = "SPACES_SECRET_KEY"
        value = digitalocean_spaces_key.api[0].secret_key
        scope = "RUN_TIME"
        type  = "SECRET"
      }

      env {
        key   = "STORAGE_SIGNING_KEY"
        value = var.runtime_secrets.api_storage_signing_key
        scope = "RUN_TIME"
        type  = "SECRET"
      }

      env {
        key   = "ATTACHMENT_OBJECT_KEY_HMAC_KEY"
        value = var.runtime_secrets.api_attachment_object_key_hmac_key
        scope = "RUN_TIME"
        type  = "SECRET"
      }

      env {
        key   = "CURSOR_SIGNING_KEY"
        value = var.runtime_secrets.api_cursor_signing_key
        scope = "RUN_TIME"
        type  = "SECRET"
      }

      env {
        key   = "IDEMPOTENCY_RECOVERY_CURRENT_KEY_ID"
        value = var.runtime_secrets.api_idempotency_current_key_id
        scope = "RUN_TIME"
        type  = "GENERAL"
      }

      env {
        key   = "IDEMPOTENCY_RECOVERY_CURRENT_KEY"
        value = var.runtime_secrets.api_idempotency_current_key
        scope = "RUN_TIME"
        type  = "SECRET"
      }

      env {
        key   = "IDEMPOTENCY_RECOVERY_PREVIOUS_KEYS"
        value = var.runtime_secrets.api_idempotency_previous_keys
        scope = "RUN_TIME"
        type  = "SECRET"
      }

      health_check {
        http_path             = "/health"
        port                  = 8000
        initial_delay_seconds = 10
        period_seconds        = 10
        timeout_seconds       = 5
        success_threshold     = 1
        failure_threshold     = 6
      }
    }

    service {
      name               = "keycloak"
      instance_count     = 1
      instance_size_slug = "apps-s-1vcpu-2gb"
      http_port          = 8080
      internal_ports     = [9000]

      image {
        registry_type = try(var.release_manifest.keycloak_image.registry_type, "DOCR")
        registry      = try(var.release_manifest.keycloak_image.registry, "invalid")
        repository    = try(var.release_manifest.keycloak_image.repository, "invalid")
        digest        = var.release_manifest.keycloak_image.digest
      }

      env {
        key   = "KC_DB_URL"
        value = "jdbc:postgresql://${digitalocean_database_cluster.shared[0].private_host}:${digitalocean_database_cluster.shared[0].port}/${digitalocean_database_db.keycloak[0].name}?sslmode=require"
        scope = "RUN_TIME"
        type  = "GENERAL"
      }

      env {
        key   = "KC_DB_USERNAME"
        value = digitalocean_database_user.keycloak[0].name
        scope = "RUN_TIME"
        type  = "GENERAL"
      }

      env {
        key   = "KC_DB_PASSWORD"
        value = digitalocean_database_user.keycloak[0].password
        scope = "RUN_TIME"
        type  = "SECRET"
      }

      env {
        key   = "KC_HOSTNAME"
        value = "$${APP_URL}/auth"
        scope = "RUN_TIME"
        type  = "GENERAL"
      }

      env {
        key   = "KC_HTTP_RELATIVE_PATH"
        value = "/auth"
        scope = "RUN_TIME"
        type  = "GENERAL"
      }

      env {
        key   = "KC_HTTP_MANAGEMENT_RELATIVE_PATH"
        value = "/management"
        scope = "RUN_TIME"
        type  = "GENERAL"
      }

      env {
        key   = "WORKLOOP_PUBLIC_URL"
        value = "$${APP_URL}"
        scope = "RUN_TIME"
        type  = "GENERAL"
      }

      health_check {
        http_path             = "/management/health/ready"
        port                  = 9000
        initial_delay_seconds = 30
        period_seconds        = 10
        timeout_seconds       = 5
        success_threshold     = 1
        failure_threshold     = 12
      }
    }

    static_site {
      name           = "web"
      source_dir     = "/"
      build_command  = "npm ci && npm run build && node scripts/verify-phase-14d-frontend.mjs --expected ${var.release_manifest.frontend_sha256} --root-expected ${var.release_manifest.frontend_root_sha256}"
      output_dir     = "dist"
      index_document = "index.html"
      error_document = "index.html"

      github {
        repo           = local.github_repository
        branch         = local.github_branch
        deploy_on_push = false
      }

      env {
        key   = "VITE_API_BASE_URL"
        value = "$${APP_URL}"
        scope = "BUILD_TIME"
        type  = "GENERAL"
      }

      env {
        key   = "VITE_OIDC_AUTHORITY"
        value = "$${APP_URL}/auth/realms/workloop-dev"
        scope = "BUILD_TIME"
        type  = "GENERAL"
      }

      env {
        key   = "VITE_OIDC_CLIENT_ID"
        value = "workloop-migration-web"
        scope = "BUILD_TIME"
        type  = "GENERAL"
      }

      env {
        key   = "VITE_OIDC_REDIRECT_URI"
        value = "$${APP_URL}/oidc/callback"
        scope = "BUILD_TIME"
        type  = "GENERAL"
      }

      env {
        key   = "VITE_OIDC_POST_LOGOUT_REDIRECT_URI"
        value = "$${APP_URL}/"
        scope = "BUILD_TIME"
        type  = "GENERAL"
      }

      env {
        key   = "VITE_OIDC_AUDIENCE"
        value = "workloop-api"
        scope = "BUILD_TIME"
        type  = "GENERAL"
      }
    }

    job {
      name               = "expiry"
      kind               = "UNSPECIFIED"
      instance_count     = 1
      instance_size_slug = "apps-s-1vcpu-0.5gb"
      run_command        = "sh -ec 'if [ \"$WORKLOOP_EXPIRY_PROCESSING_ENABLED\" = false ]; then exit 0; fi; if [ \"$WORKLOOP_EXPIRY_PROCESSING_ENABLED\" != true ]; then exit 1; fi; exec python -m app.expiry_command'"

      image {
        registry_type = try(var.release_manifest.backend_image.registry_type, "DOCR")
        registry      = try(var.release_manifest.backend_image.registry, "invalid")
        repository    = try(var.release_manifest.backend_image.repository, "invalid")
        digest        = var.release_manifest.backend_image.digest
      }

      env {
        key   = "EXPIRY_DATABASE_URL"
        value = "$${workloop-expiry.DATABASE_PRIVATE_URL}"
        scope = "RUN_TIME"
        type  = "SECRET"
      }

      env {
        key   = "WORKLOOP_EXPIRY_PROCESSING_ENABLED"
        value = tostring(local.expiry_processing_enabled)
        scope = "RUN_TIME"
        type  = "GENERAL"
      }

      env {
        key   = "WORKLOOP_EXPIRY_SCOPES_JSON"
        value = jsonencode(var.expiry_scopes)
        scope = "RUN_TIME"
        type  = "GENERAL"
      }
    }

    worker {
      name               = "file-scanner"
      instance_count     = 1
      instance_size_slug = "apps-s-1vcpu-0.5gb"
      run_command        = "python -m app.storage.scanner_worker"

      image {
        registry_type = try(var.release_manifest.backend_image.registry_type, "DOCR")
        registry      = try(var.release_manifest.backend_image.registry, "invalid")
        repository    = try(var.release_manifest.backend_image.repository, "invalid")
        digest        = var.release_manifest.backend_image.digest
      }

      termination {
        grace_period_seconds = 120
      }

      env {
        key   = "DATABASE_URL"
        value = "$${workloop-file-scanner.DATABASE_PRIVATE_URL}"
        scope = "RUN_TIME"
        type  = "SECRET"
      }

      env {
        key   = "STORAGE_BACKEND"
        value = "spaces"
        scope = "RUN_TIME"
        type  = "GENERAL"
      }

      env {
        key   = "SPACES_ENDPOINT_URL"
        value = "https://${local.resource_region}.digitaloceanspaces.com"
        scope = "RUN_TIME"
        type  = "GENERAL"
      }

      env {
        key   = "SPACES_REGION"
        value = local.resource_region
        scope = "RUN_TIME"
        type  = "GENERAL"
      }

      env {
        key   = "SPACES_BUCKET"
        value = digitalocean_spaces_bucket.shared[0].name
        scope = "RUN_TIME"
        type  = "GENERAL"
      }

      env {
        key   = "SPACES_ACCESS_KEY"
        value = digitalocean_spaces_key.file_scanner[0].access_key
        scope = "RUN_TIME"
        type  = "SECRET"
      }

      env {
        key   = "SPACES_SECRET_KEY"
        value = digitalocean_spaces_key.file_scanner[0].secret_key
        scope = "RUN_TIME"
        type  = "SECRET"
      }

      env {
        key   = "MALWARE_SCANNER_SIGNING_KEY"
        value = var.runtime_secrets.scanner_malware_signing_key
        scope = "RUN_TIME"
        type  = "SECRET"
      }

      env {
        key   = "MALWARE_SCANNER_BACKEND"
        value = "synthetic"
        scope = "RUN_TIME"
        type  = "GENERAL"
      }

      env {
        key   = "WORKLOOP_WORKER_PROCESSING_ENABLED"
        value = tostring(local.worker_processing_enabled)
        scope = "RUN_TIME"
        type  = "GENERAL"
      }
    }

    worker {
      name               = "storage-reconciler"
      instance_count     = 1
      instance_size_slug = "apps-s-1vcpu-0.5gb"
      run_command        = "python -m app.storage.reconciler"

      image {
        registry_type = try(var.release_manifest.backend_image.registry_type, "DOCR")
        registry      = try(var.release_manifest.backend_image.registry, "invalid")
        repository    = try(var.release_manifest.backend_image.repository, "invalid")
        digest        = var.release_manifest.backend_image.digest
      }

      termination {
        grace_period_seconds = 120
      }

      env {
        key   = "DATABASE_URL"
        value = "$${workloop-storage-reconciler.DATABASE_PRIVATE_URL}"
        scope = "RUN_TIME"
        type  = "SECRET"
      }

      env {
        key   = "STORAGE_BACKEND"
        value = "spaces"
        scope = "RUN_TIME"
        type  = "GENERAL"
      }

      env {
        key   = "SPACES_ENDPOINT_URL"
        value = "https://${local.resource_region}.digitaloceanspaces.com"
        scope = "RUN_TIME"
        type  = "GENERAL"
      }

      env {
        key   = "SPACES_REGION"
        value = local.resource_region
        scope = "RUN_TIME"
        type  = "GENERAL"
      }

      env {
        key   = "SPACES_BUCKET"
        value = digitalocean_spaces_bucket.shared[0].name
        scope = "RUN_TIME"
        type  = "GENERAL"
      }

      env {
        key   = "SPACES_ACCESS_KEY"
        value = digitalocean_spaces_key.storage_reconciler[0].access_key
        scope = "RUN_TIME"
        type  = "SECRET"
      }

      env {
        key   = "SPACES_SECRET_KEY"
        value = digitalocean_spaces_key.storage_reconciler[0].secret_key
        scope = "RUN_TIME"
        type  = "SECRET"
      }

      env {
        key   = "WORKLOOP_WORKER_PROCESSING_ENABLED"
        value = tostring(local.worker_processing_enabled)
        scope = "RUN_TIME"
        type  = "GENERAL"
      }
    }

    ingress {
      rule {
        component {
          name                 = "api"
          preserve_path_prefix = true
        }
        match {
          path {
            prefix = "/api"
          }
        }
      }

      rule {
        component {
          name                 = "api"
          preserve_path_prefix = true
        }
        match {
          path {
            prefix = "/health"
          }
        }
      }

      rule {
        component {
          name                 = "keycloak"
          preserve_path_prefix = true
        }
        match {
          path {
            prefix = "/auth"
          }
        }
      }

      rule {
        component {
          name = "web"
        }
        match {
          path {
            prefix = "/"
          }
        }
      }
    }
  }

  depends_on = [
    digitalocean_database_db.workloop,
    digitalocean_database_db.keycloak,
    digitalocean_database_user.workloop_migration,
    digitalocean_database_user.workloop_runtime,
    digitalocean_database_user.workloop_expiry_processing,
    digitalocean_database_user.workloop_file_scanner,
    digitalocean_database_user.workloop_storage_reconciler,
    digitalocean_database_user.keycloak,
    digitalocean_spaces_bucket.shared,
    digitalocean_spaces_key.api,
    digitalocean_spaces_key.file_scanner,
    digitalocean_spaces_key.storage_reconciler,
    digitalocean_spaces_key.object_backup,
    terraform_data.phase_14_guard,
  ]
}

resource "digitalocean_database_firewall" "app_only" {
  count      = local.enabled ? 1 : 0
  cluster_id = digitalocean_database_cluster.shared[0].id

  rule {
    type  = "app"
    value = digitalocean_app.shared[0].id
  }
}

resource "digitalocean_project_resources" "shared" {
  count   = local.enabled ? 1 : 0
  project = data.digitalocean_project.shared[0].id
  resources = [
    digitalocean_spaces_bucket.shared[0].urn,
    digitalocean_database_cluster.shared[0].urn,
    digitalocean_app.shared[0].urn,
  ]
}
