variable "provisioning_authorized" {
  description = "Allows the reviewed shared-development resources to enter a plan."
  type        = bool
  default     = false

  validation {
    condition = !var.provisioning_authorized || alltrue([
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
    error_message = "Provisioning requires every field in the reviewed Phase 14 target approval."
  }

  validation {
    condition = !var.provisioning_authorized || try(
      var.operator_access != null && alltrue([
        for role in [
          var.operator_access.infrastructure_custodian,
          var.operator_access.security_custodian,
          var.operator_access.application_operator,
          var.operator_access.incident_operator,
          var.operator_access.release_reviewer,
          ] : (
          length(trimspace(role.primary_name)) > 0 &&
          length(trimspace(role.primary_account_reference)) > 0 &&
          role.primary_mfa &&
          length(trimspace(role.backup_name)) > 0 &&
          length(trimspace(role.backup_account_reference)) > 0 &&
          role.backup_mfa &&
          role.primary_name != role.backup_name &&
          role.primary_account_reference != role.backup_account_reference
        )
      ]),
      false,
    )
    error_message = "Provisioning requires distinct named primary and backup least-privilege accounts with MFA for all five operator roles."
  }

  validation {
    condition = !var.provisioning_authorized || try(
      var.runtime_secrets != null && alltrue([
        for value in [
          var.runtime_secrets.api_storage_signing_key,
          var.runtime_secrets.api_attachment_object_key_hmac_key,
          var.runtime_secrets.api_cursor_signing_key,
          var.runtime_secrets.api_idempotency_current_key_id,
          var.runtime_secrets.api_idempotency_current_key,
          var.runtime_secrets.api_idempotency_previous_keys,
          var.runtime_secrets.scanner_malware_signing_key,
        ] : length(trimspace(value)) > 0
      ]),
      false,
    )
    error_message = "Provisioning requires the complete encrypted runtime-secret input."
  }

  validation {
    condition     = !var.provisioning_authorized || var.release_manifest != null
    error_message = "Provisioning requires one complete deployable release manifest."
  }
}

variable "configuration_ceiling_usd" {
  description = "Maximum fixed monthly configuration cost before tax and overages."
  type        = number
  default     = 70

  validation {
    condition     = var.configuration_ceiling_usd == 70
    error_message = "The shared-development configuration ceiling is exactly USD 70."
  }
}

variable "release_promoted" {
  description = "Disables maintenance mode only after every release gate passes."
  type        = bool
  default     = false

  validation {
    condition     = !var.release_promoted || var.release_promotion_approved
    error_message = "Release promotion requires its separate recorded approval."
  }
}

variable "release_promotion_approved" {
  description = "Confirms a named owner approved the exact release promotion."
  type        = bool
  default     = false
}

variable "release_manifest" {
  description = "Reviewed immutable artifacts and source digests for one deployment."
  type = object({
    release_id = string
    deployable = bool
    git_commit = string
    backend_image = object({
      registry_type = string
      registry      = string
      repository    = string
      digest        = string
    })
    keycloak_image = object({
      registry_type = string
      registry      = string
      repository    = string
      digest        = string
    })
    frontend_sha256      = string
    frontend_root_sha256 = string
    dependency_lock_sha256 = object({
      frontend    = string
      backend     = string
      backend_dev = string
    })
    terraform_sha256 = string
    app_spec_sha256  = string
    alembic_head     = string
  })
  default   = null
  nullable  = true
  sensitive = false

  validation {
    condition = var.release_manifest == null ? true : (
      var.release_manifest.deployable &&
      can(regex("^[a-z0-9][a-z0-9._-]{2,79}$", var.release_manifest.release_id)) &&
      can(regex("^[0-9a-f]{40}$", var.release_manifest.git_commit)) &&
      var.release_manifest.alembic_head == "e8a1c3f5b7d9" &&
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
      ])
    )
    error_message = "The release manifest must contain one full commit, immutable SHA-256 digests, and Alembic head e8a1c3f5b7d9."
  }
}

variable "expiry_scopes" {
  description = "Synthetic company and optional branch scopes processed by one expiry invocation."
  type = list(object({
    company_id = string
    branch_id  = optional(string)
  }))
  default = []

  validation {
    condition = alltrue([
      for scope in var.expiry_scopes :
      can(regex("^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$", scope.company_id)) &&
      (scope.branch_id == null || can(regex("^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$", scope.branch_id)))
    ])
    error_message = "Expiry scopes must contain lowercase UUID company IDs and optional branch IDs."
  }
}

variable "approval" {
  description = "Non-secret references and named custodians for the exact approved target."
  type = object({
    target_manifest_id       = string
    owner_approval_reference = string
    approved_on              = string
    price_reviewed_on        = string
    retention_review_due_on  = string
    state_custodian          = string
    state_path_reference     = string
    credential_custodian     = string
    infrastructure_owner     = string
    security_owner           = string
    application_owner        = string
    incident_owner           = string
    release_reviewer         = string
    backup_custodian         = string
    variable_charge_owner    = string
    cleanup_manifest_id      = string
  })
  default   = null
  nullable  = true
  sensitive = false

  validation {
    condition = var.approval == null ? true : alltrue([
      for value in [var.approval.approved_on, var.approval.price_reviewed_on, var.approval.retention_review_due_on] :
      can(regex("^[0-9]{4}-[0-9]{2}-[0-9]{2}$", value))
    ])
    error_message = "Approval, price review, and retention review dates must use YYYY-MM-DD."
  }
}

variable "operator_access" {
  description = "Named primary and backup accounts with MFA for every required operator role."
  type = object({
    infrastructure_custodian = object({
      primary_name              = string
      primary_account_reference = string
      primary_mfa               = bool
      backup_name               = string
      backup_account_reference  = string
      backup_mfa                = bool
    })
    security_custodian = object({
      primary_name              = string
      primary_account_reference = string
      primary_mfa               = bool
      backup_name               = string
      backup_account_reference  = string
      backup_mfa                = bool
    })
    application_operator = object({
      primary_name              = string
      primary_account_reference = string
      primary_mfa               = bool
      backup_name               = string
      backup_account_reference  = string
      backup_mfa                = bool
    })
    incident_operator = object({
      primary_name              = string
      primary_account_reference = string
      primary_mfa               = bool
      backup_name               = string
      backup_account_reference  = string
      backup_mfa                = bool
    })
    release_reviewer = object({
      primary_name              = string
      primary_account_reference = string
      primary_mfa               = bool
      backup_name               = string
      backup_account_reference  = string
      backup_mfa                = bool
    })
  })
  default   = null
  nullable  = true
  sensitive = false

  validation {
    condition = var.operator_access == null ? true : alltrue([
      for role in [
        var.operator_access.infrastructure_custodian,
        var.operator_access.security_custodian,
        var.operator_access.application_operator,
        var.operator_access.incident_operator,
        var.operator_access.release_reviewer,
        ] : (
        length(trimspace(role.primary_name)) > 0 &&
        length(trimspace(role.primary_account_reference)) > 0 &&
        role.primary_mfa &&
        length(trimspace(role.backup_name)) > 0 &&
        length(trimspace(role.backup_account_reference)) > 0 &&
        role.backup_mfa &&
        role.primary_name != role.backup_name &&
        role.primary_account_reference != role.backup_account_reference
      )
    ])
    error_message = "Every operator role requires distinct named primary and backup least-privilege accounts with MFA."
  }
}

variable "runtime_secrets" {
  description = "Encrypted application settings supplied only for an approved enabled plan."
  type = object({
    api_storage_signing_key            = string
    api_attachment_object_key_hmac_key = string
    api_cursor_signing_key             = string
    api_idempotency_current_key_id     = string
    api_idempotency_current_key        = string
    api_idempotency_previous_keys      = string
    scanner_malware_signing_key        = string
  })
  default   = null
  nullable  = true
  sensitive = true
}
