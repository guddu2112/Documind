# Role assignments for service-to-service access via managed identities.
# This module consolidates all RBAC assignments in one place for auditability.

resource "azurerm_role_assignment" "assignments" {
  for_each = { for idx, ra in var.role_assignments : "${idx}-${ra.role_name}" => ra }

  scope                = each.value.scope
  role_definition_name = each.value.role_name
  principal_id         = each.value.principal_id
  description          = each.value.description
}
