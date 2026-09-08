locals {
  enabled                   = var.provisioning_authorized
  app_region                = "fra"
  resource_region           = "fra1"
  app_name                  = "workloop-phase-6g"
  project_name              = "workloop-clinic-dev"
  github_repository         = "AadhikR/workloop-clinic"
  github_branch             = "migration/fastapi-keycloak"
  estimated_monthly_usd     = 55.15
  estimated_test_window_usd = local.estimated_monthly_usd / (28 * 24) * var.test_window_hours
}

resource "terraform_data" "phase_6g_guard" {
  input = {
    budget_ceiling_usd = var.budget_ceiling_usd
    test_window_hours  = var.test_window_hours
  }

  lifecycle {
    precondition {
      condition = !var.provisioning_authorized || alltrue([
        var.spend_alert_confirmed,
        var.github_app_repository_only_confirmed,
        var.project_isolation_confirmed,
      ])
      error_message = "Phase 6G provisioning requires the spend alert, repository-only GitHub access, and isolated project confirmations."
    }
    precondition {
      condition     = var.budget_ceiling_usd == 20
      error_message = "The authorized Phase 6G budget ceiling is exactly 20 USD."
    }
    precondition {
      condition     = var.test_window_hours > 0 && var.test_window_hours <= 72
      error_message = "The Phase 6G test window must be no longer than 72 hours."
    }
    precondition {
      condition = !var.provisioning_authorized || can(
        regex("^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$", var.teardown_deadline_utc)
      )
      error_message = "An authorized run requires an explicit UTC teardown deadline."
    }
    precondition {
      condition = !var.provisioning_authorized || (
        var.keycloak_bootstrap_admin_password != null &&
        length(var.keycloak_bootstrap_admin_password) >= 20 &&
        var.synthetic_user_password != null &&
        length(var.synthetic_user_password) >= 20
      )
      error_message = "An authorized run requires both temporary passwords with at least 20 characters."
    }
    precondition {
      condition     = !var.public_exposure_enabled || var.admin_mfa_gate_armed
      error_message = "Keycloak cannot be exposed until the administrator TOTP gate is armed."
    }
  }
}

data "digitalocean_project" "workloop" {
  count = local.enabled ? 1 : 0
  name  = local.project_name
}

resource "digitalocean_vpc" "proof" {
  count       = local.enabled ? 1 : 0
  name        = "workloop-phase-6g"
  region      = local.resource_region
  description = "Temporary private network for the Phase 6G architecture proof"
}

resource "digitalocean_database_cluster" "proof" {
  count                = local.enabled ? 1 : 0
  name                 = "workloop-phase-6g"
  engine               = "pg"
  version              = "16"
  size                 = "db-s-1vcpu-1gb"
  region               = local.resource_region
  node_count           = 1
  private_network_uuid = digitalocean_vpc.proof[0].id
  project_id           = data.digitalocean_project.workloop[0].id

  storage_autoscale {
    enabled = false
  }

  depends_on = [terraform_data.phase_6g_guard]
}

resource "digitalocean_database_db" "workloop" {
  count      = local.enabled ? 1 : 0
  cluster_id = digitalocean_database_cluster.proof[0].id
  name       = "workloop"
}

resource "digitalocean_database_db" "keycloak" {
  count      = local.enabled ? 1 : 0
  cluster_id = digitalocean_database_cluster.proof[0].id
  name       = "keycloak"
}

resource "digitalocean_database_user" "workloop_migration" {
  count      = local.enabled ? 1 : 0
  cluster_id = digitalocean_database_cluster.proof[0].id
  name       = "workloop_migration"
}

resource "digitalocean_database_user" "workloop_runtime" {
  count      = local.enabled ? 1 : 0
  cluster_id = digitalocean_database_cluster.proof[0].id
  name       = "workloop_runtime"
}

resource "digitalocean_database_user" "keycloak" {
  count      = local.enabled ? 1 : 0
  cluster_id = digitalocean_database_cluster.proof[0].id
  name       = "keycloak"
}

resource "digitalocean_spaces_bucket" "proof" {
  count         = local.enabled ? 1 : 0
  name          = "workloop-phase-6g-${substr(data.digitalocean_project.workloop[0].owner_uuid, 0, 8)}"
  region        = local.resource_region
  acl           = "private"
  force_destroy = true

  versioning {
    enabled = false
  }

  depends_on = [terraform_data.phase_6g_guard]
}

resource "digitalocean_spaces_key" "api" {
  count = local.enabled ? 1 : 0
  name  = "workloop-phase-6g-api"

  grant {
    bucket     = digitalocean_spaces_bucket.proof[0].name
    permission = "readwrite"
  }
}

resource "digitalocean_app" "proof" {
  count      = local.enabled ? 1 : 0
  project_id = data.digitalocean_project.workloop[0].id

  spec {
    name   = local.app_name
    region = local.app_region

    maintenance {
      enabled = !var.public_exposure_enabled
    }

    alert {
      rule = "DEPLOYMENT_FAILED"
    }

    alert {
      rule = "DOMAIN_FAILED"
    }

    vpc {
      id = digitalocean_vpc.proof[0].id
    }

    database {
      name         = "workloop-admin"
      engine       = "PG"
      production   = true
      cluster_name = digitalocean_database_cluster.proof[0].name
      db_name      = digitalocean_database_db.workloop[0].name
      db_user      = digitalocean_database_cluster.proof[0].user
    }

    database {
      name         = "workloop-migration"
      engine       = "PG"
      production   = true
      cluster_name = digitalocean_database_cluster.proof[0].name
      db_name      = digitalocean_database_db.workloop[0].name
      db_user      = digitalocean_database_user.workloop_migration[0].name
    }

    database {
      name         = "workloop-runtime"
      engine       = "PG"
      production   = true
      cluster_name = digitalocean_database_cluster.proof[0].name
      db_name      = digitalocean_database_db.workloop[0].name
      db_user      = digitalocean_database_user.workloop_runtime[0].name
    }

    database {
      name         = "keycloak-admin"
      engine       = "PG"
      production   = true
      cluster_name = digitalocean_database_cluster.proof[0].name
      db_name      = digitalocean_database_db.keycloak[0].name
      db_user      = digitalocean_database_cluster.proof[0].user
    }

    database {
      name         = "keycloak-db"
      engine       = "PG"
      production   = true
      cluster_name = digitalocean_database_cluster.proof[0].name
      db_name      = digitalocean_database_db.keycloak[0].name
      db_user      = digitalocean_database_user.keycloak[0].name
    }

    job {
      name               = "database-migrate"
      kind               = "PRE_DEPLOY"
      instance_size_slug = "apps-s-1vcpu-1gb"
      run_command        = "python -m app.db.cloud_bootstrap && alembic upgrade head && python -m app.db.cloud_seed"
      source_dir         = "backend"
      dockerfile_path    = "Dockerfile"

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
      instance_size_slug = "apps-s-1vcpu-1gb"
      http_port          = 8000
      source_dir         = "backend"
      dockerfile_path    = "Dockerfile"

      github {
        repo           = local.github_repository
        branch         = local.github_branch
        deploy_on_push = false
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
        value = digitalocean_spaces_bucket.proof[0].name
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
    }

    service {
      name               = "keycloak"
      instance_count     = 1
      instance_size_slug = "apps-s-1vcpu-2gb"
      http_port          = 8080
      internal_ports     = [9000]
      source_dir         = "keycloak"
      dockerfile_path    = "Dockerfile"

      github {
        repo           = local.github_repository
        branch         = local.github_branch
        deploy_on_push = false
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

      env {
        key   = "KC_DB_URL"
        value = "jdbc:postgresql://${digitalocean_database_cluster.proof[0].private_host}:${digitalocean_database_cluster.proof[0].port}/${digitalocean_database_db.keycloak[0].name}?sslmode=require"
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
        key   = "KC_BOOTSTRAP_ADMIN_USERNAME"
        value = var.keycloak_bootstrap_admin_username
        scope = "RUN_TIME"
        type  = "GENERAL"
      }

      env {
        key   = "KC_BOOTSTRAP_ADMIN_PASSWORD"
        value = var.keycloak_bootstrap_admin_password
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
        key   = "WORKLOOP_SYNTHETIC_USER_PASSWORD"
        value = var.synthetic_user_password
        scope = "RUN_TIME"
        type  = "SECRET"
      }
    }

    static_site {
      name           = "web"
      source_dir     = "/"
      build_command  = "npm ci && npm run build:migration"
      output_dir     = "dist-migration"
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
        value = "$${APP_URL}/auth/callback"
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
    digitalocean_database_user.workloop_migration,
    digitalocean_database_user.workloop_runtime,
    digitalocean_database_user.keycloak,
    digitalocean_spaces_key.api,
    terraform_data.phase_6g_guard,
  ]
}

resource "digitalocean_database_firewall" "proof" {
  count      = local.enabled ? 1 : 0
  cluster_id = digitalocean_database_cluster.proof[0].id

  rule {
    type  = "app"
    value = digitalocean_app.proof[0].id
  }
}

resource "digitalocean_project_resources" "spaces" {
  count   = local.enabled ? 1 : 0
  project = data.digitalocean_project.workloop[0].id
  resources = [
    digitalocean_spaces_bucket.proof[0].urn,
  ]
}
