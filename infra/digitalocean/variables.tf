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
