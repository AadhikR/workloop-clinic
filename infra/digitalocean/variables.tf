variable "provisioning_authorized" {
  description = "Set true only for the approved Phase 6G test window."
  type        = bool
  default     = false
}

variable "spend_alert_confirmed" {
  description = "Confirms the DigitalOcean team has the approved 20 USD spend alert."
  type        = bool
  default     = false
}

variable "github_app_repository_only_confirmed" {
  description = "Confirms App Platform GitHub access is limited to AadhikR/workloop-clinic."
  type        = bool
  default     = false
}

variable "project_isolation_confirmed" {
  description = "Confirms workloop-clinic-dev exists and contains no unrelated resources."
  type        = bool
  default     = false
}

variable "admin_mfa_gate_armed" {
  description = "Confirms the Keycloak master administrator must configure TOTP before console access."
  type        = bool
  default     = false
}

variable "public_exposure_enabled" {
  description = "Disables maintenance mode only after the administrator MFA check passes."
  type        = bool
  default     = false
}

variable "budget_ceiling_usd" {
  description = "Absolute total Phase 6G DigitalOcean ceiling."
  type        = number
  default     = 20
}

variable "test_window_hours" {
  description = "Maximum elapsed time before teardown."
  type        = number
  default     = 72
}

variable "teardown_deadline_utc" {
  description = "Explicit UTC teardown deadline for an authorized run."
  type        = string
  default     = ""
}

variable "keycloak_bootstrap_admin_username" {
  description = "Temporary Keycloak master administrator username."
  type        = string
  default     = "workloop-phase6g-admin"
}

variable "keycloak_bootstrap_admin_password" {
  description = "Temporary Keycloak master administrator password supplied outside source control."
  type        = string
  sensitive   = true
  default     = null
  nullable    = true
}

variable "synthetic_user_password" {
  description = "Password for the synthetic Phase 6G login supplied outside source control."
  type        = string
  sensitive   = true
  default     = null
  nullable    = true
}
