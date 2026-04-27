variable "resource_group_name" {
  type        = string
  description = "Resource group name (used for scoping role assignments)"
}

variable "resource_group_id" {
  type        = string
  description = "Resource group ID for scoping role assignments"
}

variable "role_assignments" {
  type = list(object({
    principal_id = string
    role_name    = string
    scope        = string
    description  = optional(string, "")
  }))
  description = "List of role assignments to create"
  default     = []
}
