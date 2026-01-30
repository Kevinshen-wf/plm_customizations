"""
Setup functions for PLM Customizations
"""
import frappe


def after_install():
    """Run after app installation or migration"""
    configure_workspace_roles(check_permission=False)
    setup_plm_custom_fields()
    frappe.db.commit()


def setup_plm_custom_fields():
    """Setup all PLM custom fields on various DocTypes"""
    try:
        # Setup BOM PLM fields
        from plm_customizations.api.bom_version import ensure_bom_custom_fields, ensure_bom_version_table
        ensure_bom_custom_fields()
        ensure_bom_version_table()
    except Exception as e:
        frappe.logger().error(f"Error setting up BOM PLM fields: {str(e)}")
    
    try:
        # Setup Work Order PLM fields
        from plm_customizations.api.work_order_version import ensure_work_order_custom_fields
        ensure_work_order_custom_fields()
    except Exception as e:
        frappe.logger().error(f"Error setting up Work Order PLM fields: {str(e)}")


@frappe.whitelist()
def configure_workspace_roles(check_permission=True):
    """
    Configure workspace roles to restrict Mechanical Engineer to only see Home workspace.
    
    Strategy:
    - For all workspaces except Home, add roles that exclude Mechanical Engineer
    - Home workspace remains accessible to all (roles empty)
    
    Can be called from console: frappe.call('plm_customizations.setup.configure_workspace_roles')
    
    Args:
        check_permission: If True, check for Workspace write permission. Set to False for after_install.
    """
    if check_permission and not frappe.has_permission("Workspace", "write"):
        frappe.throw("You need Workspace Manager permission to configure workspace roles")
    
    # List of workspaces that should be hidden from Mechanical Engineer
    # These include ERPNext and Frappe workspaces
    workspaces_to_restrict = [
        # ERPNext workspaces
        "Accounting",
        "Payables",
        "Receivables",
        "Financial Reports",
        "Buying",
        "Selling",
        "Stock",
        "Manufacturing",
        "Assets",
        "Projects",
        "CRM",
        "Support",
        "Quality",
        "ERPNext Settings",
        "ERPNext Integrations",
        # Frappe system workspaces (should be hidden from regular users)
        "Build",
        "Tools",
        "Users",
        "Website",
        "Integrations"
    ]
    
    # Workspaces that Mechanical Engineer should be able to see
    # We need to add Mechanical Engineer to these workspaces' roles
    workspaces_for_mechanical_engineer = [
        "Item"  # PLM Item workspace - Mechanical Engineer needs to manage items
    ]
    
    # Roles that should have access to these workspaces (excluding Mechanical Engineer)
    standard_roles = [
        "System Manager",
        "Accounts Manager",
        "Accounts User",
        "Sales Manager",
        "Sales User",
        "Purchase Manager",
        "Purchase User",
        "Stock Manager",
        "Stock User",
        "Manufacturing Manager",
        "Manufacturing User",
        "Item Manager",
        "Quality Manager",
        "Projects Manager",
        "Projects User",
        "Support Team",
        "HR Manager",
        "HR User"
    ]
    
    for workspace_name in workspaces_to_restrict:
        try:
            if frappe.db.exists("Workspace", workspace_name):
                workspace = frappe.get_doc("Workspace", workspace_name)
                
                # Clear existing roles
                workspace.roles = []
                
                # Add standard roles (excluding Mechanical Engineer)
                for role in standard_roles:
                    if frappe.db.exists("Role", role):
                        workspace.append("roles", {"role": role})
                
                workspace.flags.ignore_permissions = True
                workspace.save()
                
                frappe.logger().info(f"Configured roles for workspace: {workspace_name}")
        except Exception as e:
            frappe.logger().error(f"Error configuring workspace {workspace_name}: {str(e)}")
    
    # Add Mechanical Engineer to specific workspaces they need access to
    for workspace_name in workspaces_for_mechanical_engineer:
        try:
            if frappe.db.exists("Workspace", workspace_name):
                workspace = frappe.get_doc("Workspace", workspace_name)
                
                # Get current roles
                current_roles = [r.role for r in workspace.roles]
                
                # Add Mechanical Engineer if not already present
                if "Mechanical Engineer" not in current_roles:
                    workspace.append("roles", {"role": "Mechanical Engineer"})
                    workspace.flags.ignore_permissions = True
                    workspace.save()
                    frappe.logger().info(f"Added Mechanical Engineer to workspace: {workspace_name}")
        except Exception as e:
            frappe.logger().error(f"Error adding ME to workspace {workspace_name}: {str(e)}")
    
    frappe.msgprint("Workspace roles configured for Mechanical Engineer")


def remove_mechanical_engineer_workspace_restrictions():
    """
    Remove workspace restrictions for Mechanical Engineer (utility function).
    This can be called to reset workspace visibility.
    """
    workspaces = frappe.get_all("Workspace", filters={"public": 1}, pluck="name")
    
    for workspace_name in workspaces:
        try:
            workspace = frappe.get_doc("Workspace", workspace_name)
            workspace.roles = []
            workspace.flags.ignore_permissions = True
            workspace.save()
        except Exception as e:
            frappe.logger().error(f"Error resetting workspace {workspace_name}: {str(e)}")
