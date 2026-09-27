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

  operator_access_complete = var.operator_access != null && alltrue([
    length(trimspace(try(var.operator_access.infrastructure_custodian.primary_name, ""))) > 0,
    length(trimspace(try(var.operator_access.infrastructure_custodian.primary_account_reference, ""))) > 0,
    try(var.operator_access.infrastructure_custodian.primary_mfa, false),
    length(trimspace(try(var.operator_access.infrastructure_custodian.backup_name, ""))) > 0,
    length(trimspace(try(var.operator_access.infrastructure_custodian.backup_account_reference, ""))) > 0,
    try(var.operator_access.infrastructure_custodian.backup_mfa, false),
    length(trimspace(try(var.operator_access.security_custodian.primary_name, ""))) > 0,
    length(trimspace(try(var.operator_access.security_custodian.primary_account_reference, ""))) > 0,
    try(var.operator_access.security_custodian.primary_mfa, false),
    length(trimspace(try(var.operator_access.security_custodian.backup_name, ""))) > 0,
    length(trimspace(try(var.operator_access.security_custodian.backup_account_reference, ""))) > 0,
    try(var.operator_access.security_custodian.backup_mfa, false),
    length(trimspace(try(var.operator_access.application_operator.primary_name, ""))) > 0,
    length(trimspace(try(var.operator_access.application_operator.primary_account_reference, ""))) > 0,
    try(var.operator_access.application_operator.primary_mfa, false),
    length(trimspace(try(var.operator_access.application_operator.backup_name, ""))) > 0,
    length(trimspace(try(var.operator_access.application_operator.backup_account_reference, ""))) > 0,
    try(var.operator_access.application_operator.backup_mfa, false),
    length(trimspace(try(var.operator_access.incident_operator.primary_name, ""))) > 0,
    length(trimspace(try(var.operator_access.incident_operator.primary_account_reference, ""))) > 0,
    try(var.operator_access.incident_operator.primary_mfa, false),
    length(trimspace(try(var.operator_access.incident_operator.backup_name, ""))) > 0,
    length(trimspace(try(var.operator_access.incident_operator.backup_account_reference, ""))) > 0,
    try(var.operator_access.incident_operator.backup_mfa, false),
    length(trimspace(try(var.operator_access.release_reviewer.primary_name, ""))) > 0,
    length(trimspace(try(var.operator_access.release_reviewer.primary_account_reference, ""))) > 0,
    try(var.operator_access.release_reviewer.primary_mfa, false),
    length(trimspace(try(var.operator_access.release_reviewer.backup_name, ""))) > 0,
    length(trimspace(try(var.operator_access.release_reviewer.backup_account_reference, ""))) > 0,
    try(var.operator_access.release_reviewer.backup_mfa, false),
  ])

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

  enabled = var.provisioning_authorized && local.approval_complete && local.operator_access_complete && local.runtime_secrets_complete
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
    app_name              = local.app_name
    database_cluster_name = local.database_cluster_name
    estimated_monthly_usd = local.estimated_monthly_usd
    spaces_bucket_name    = local.spaces_bucket_name
  }

  lifecycle {
    precondition {
      condition     = !var.provisioning_authorized || local.approval_complete
      error_message = "Provisioning requires every field in the reviewed Phase 14 target approval."
    }
    precondition {
      condition     = !var.provisioning_authorized || local.operator_access_complete
      error_message = "Provisioning requires distinct named primary and backup least-privilege accounts with MFA for all five operator roles."
    }
    precondition {
      condition     = !var.provisioning_authorized || local.runtime_secrets_complete
      error_message = "Provisioning requires the complete encrypted runtime-secret input."
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
      condition     = !var.release_promoted || var.release_promotion_approved
      error_message = "The provider default address must stay in maintenance mode without a recorded release promotion approval."
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

  storage_autoscale {
    enabled = false
  }

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
      name         = "keycloak"
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
      source_dir         = "backend"
      dockerfile_path    = "backend/Dockerfile"

      github {
        repo           = local.github_repository
        branch         = local.github_branch
        deploy_on_push = false
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
    }

    service {
      name               = "api"
      instance_count     = 1
      instance_size_slug = "apps-s-1vcpu-1gb-fixed"
      http_port          = 8000
      source_dir         = "backend"
      dockerfile_path    = "backend/Dockerfile"

      github {
        repo           = local.github_repository
        branch         = local.github_branch
        deploy_on_push = false
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
      source_dir         = "keycloak"
      dockerfile_path    = "keycloak/Dockerfile"

      github {
        repo           = local.github_repository
        branch         = local.github_branch
        deploy_on_push = false
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
      build_command  = "npm ci && npm run build"
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
      run_command        = "python -m app.expiry_command"
      source_dir         = "backend"
      dockerfile_path    = "backend/Dockerfile"

      github {
        repo           = local.github_repository
        branch         = local.github_branch
        deploy_on_push = false
      }

      env {
        key   = "EXPIRY_DATABASE_URL"
        value = "$${workloop-expiry.DATABASE_PRIVATE_URL}"
        scope = "RUN_TIME"
        type  = "SECRET"
      }
    }

    worker {
      name               = "file-scanner"
      instance_count     = 1
      instance_size_slug = "apps-s-1vcpu-0.5gb"
      run_command        = "python -m app.storage.scanner_worker"
      source_dir         = "backend"
      dockerfile_path    = "backend/Dockerfile"

      github {
        repo           = local.github_repository
        branch         = local.github_branch
        deploy_on_push = false
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
    }

    worker {
      name               = "storage-reconciler"
      instance_count     = 1
      instance_size_slug = "apps-s-1vcpu-0.5gb"
      run_command        = "python -m app.storage.reconciler"
      source_dir         = "backend"
      dockerfile_path    = "backend/Dockerfile"

      github {
        repo           = local.github_repository
        branch         = local.github_branch
        deploy_on_push = false
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
