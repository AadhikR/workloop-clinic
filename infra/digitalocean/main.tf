locals {
  enabled               = var.provisioning_authorized && local.approval_complete
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
    digitalocean_spaces_bucket.shared,
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
