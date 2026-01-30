import frappe
import json
from frappe import _
from frappe.utils import now_datetime


def get_bom_snapshot(bom_name):
    """
    Get a snapshot of BOM data including items.
    Returns a dict that can be stored in BOM Version.
    """
    bom = frappe.get_doc("BOM", bom_name)
    bom_data = bom.as_dict()
    
    # Remove system fields
    for key in ['modified', 'creation', 'modified_by', 'owner', '_user_tags', '_comments', '_assign', '_liked_by']:
        bom_data.pop(key, None)
    
    return bom_data


def ensure_bom_version_table():
    """
    Create BOM Version table if it doesn't exist.
    Uses Custom DocType created via Frappe.
    """
    if not frappe.db.exists("DocType", "BOM Version"):
        # Create the DocType programmatically
        doc = frappe.get_doc({
            "doctype": "DocType",
            "name": "BOM Version",
            "module": "PLM Customizations",
            "custom": 1,
            "autoname": "format:{bom}-v{version}",
            "naming_rule": "Expression",
            "fields": [
                {"fieldname": "bom", "label": "BOM", "fieldtype": "Link", "options": "BOM", "reqd": 1, "in_list_view": 1},
                {"fieldname": "version", "label": "Version", "fieldtype": "Int", "reqd": 1, "in_list_view": 1, "read_only": 1},
                {"fieldname": "status", "label": "Status", "fieldtype": "Select", "options": "Draft\nPublished\nBlocked", "default": "Draft", "in_list_view": 1},
                {"fieldname": "column_break_1", "fieldtype": "Column Break"},
                {"fieldname": "published_date", "label": "Published Date", "fieldtype": "Datetime", "read_only": 1},
                {"fieldname": "published_by", "label": "Published By", "fieldtype": "Link", "options": "User", "read_only": 1},
                {"fieldname": "section_break_snapshot", "label": "Version Snapshot", "fieldtype": "Section Break"},
                {"fieldname": "bom_data", "label": "BOM Data (JSON)", "fieldtype": "Long Text", "read_only": 1, "hidden": 1},
                {"fieldname": "notes", "label": "Version Notes", "fieldtype": "Text"}
            ],
            "permissions": [
                {"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1},
                {"role": "Manufacturing Manager", "read": 1, "write": 1, "create": 1},
                {"role": "Manufacturing User", "read": 1},
                {"role": "Mechanical Engineer", "read": 1, "write": 1, "create": 1}
            ]
        })
        doc.insert(ignore_permissions=True)
        frappe.db.commit()


def ensure_bom_custom_fields():
    """
    Create custom fields on BOM if they don't exist.
    """
    fields_to_create = [
        {"dt": "BOM", "fieldname": "current_version", "label": "Current Version", "fieldtype": "Int", 
         "insert_after": "naming_series", "default": "0", "read_only": 1, "bold": 1},
        {"dt": "BOM", "fieldname": "plm_status", "label": "PLM Status", "fieldtype": "Select",
         "options": "Draft\nPublished\nBlocked", "insert_after": "current_version", "default": "Draft", "read_only": 1},
        {"dt": "BOM", "fieldname": "bom_published_date", "label": "Published Date", "fieldtype": "Datetime",
         "insert_after": "plm_status", "read_only": 1},
        {"dt": "BOM", "fieldname": "bom_published_by", "label": "Published By", "fieldtype": "Link",
         "options": "User", "insert_after": "bom_published_date", "read_only": 1}
    ]
    
    for field in fields_to_create:
        field_name = f"BOM-{field['fieldname']}"
        if not frappe.db.exists("Custom Field", field_name):
            cf = frappe.get_doc({"doctype": "Custom Field", **field})
            cf.insert(ignore_permissions=True)
    
    frappe.db.commit()


@frappe.whitelist()
def setup_bom_plm_fields():
    """
    Setup all required fields and DocTypes for BOM PLM version control.
    Call this once to initialize the system.
    """
    ensure_bom_custom_fields()
    ensure_bom_version_table()
    return {"success": True, "message": "BOM PLM fields and DocTypes created successfully"}


@frappe.whitelist()
def has_bom_publish_permission():
    """
    Check if user has permission to publish/block BOMs.
    """
    user_roles = frappe.get_roles(frappe.session.user)
    allowed_roles = ["System Manager", "Manufacturing Manager", "Mechanical Engineer"]
    return any(role in user_roles for role in allowed_roles)


@frappe.whitelist()
def save_bom_changes(bom_name, changes=None):
    """
    Save changes to a submitted BOM using direct database updates.
    This allows modifying a submitted BOM without unsubmitting it.
    """
    if not has_bom_publish_permission():
        return {"success": False, "error": _("You don't have permission to modify BOMs")}
    
    if not changes:
        return {"success": True, "message": _("No changes to save")}
    
    try:
        if isinstance(changes, str):
            changes = json.loads(changes)
        
        bom = frappe.get_doc("BOM", bom_name)
        
        # Update basic fields
        basic_fields = ['quantity', 'rm_cost_as_per', 'buying_price_list']
        for field in basic_fields:
            if field in changes and changes[field] is not None:
                frappe.db.set_value("BOM", bom_name, field, changes[field], update_modified=True)
        
        # Update items - delete existing and recreate
        if 'items' in changes and changes['items']:
            # Delete existing items
            frappe.db.delete("BOM Item", {"parent": bom_name})
            
            # Insert new items
            for idx, item in enumerate(changes['items'], 1):
                item_doc = frappe.get_doc({
                    "doctype": "BOM Item",
                    "parent": bom_name,
                    "parentfield": "items",
                    "parenttype": "BOM",
                    "idx": idx,
                    "item_code": item.get("item_code"),
                    "qty": item.get("qty", 1),
                    "uom": item.get("uom"),
                    "rate": item.get("rate", 0),
                    "amount": item.get("amount", 0),
                    "source_warehouse": item.get("source_warehouse")
                })
                item_doc.db_insert()
        
        # Update operations - delete existing and recreate
        if 'operations' in changes and changes['operations']:
            # Delete existing operations
            frappe.db.delete("BOM Operation", {"parent": bom_name})
            
            # Insert new operations
            for idx, op in enumerate(changes['operations'], 1):
                op_doc = frappe.get_doc({
                    "doctype": "BOM Operation",
                    "parent": bom_name,
                    "parentfield": "operations",
                    "parenttype": "BOM",
                    "idx": idx,
                    "operation": op.get("operation"),
                    "workstation": op.get("workstation"),
                    "time_in_mins": op.get("time_in_mins", 0),
                    "operating_cost": op.get("operating_cost", 0)
                })
                op_doc.db_insert()
        
        frappe.db.commit()
        return {"success": True, "message": _("Changes saved successfully")}
        
    except Exception as e:
        frappe.log_error(f"Error saving BOM changes: {str(e)}")
        return {"success": False, "error": str(e)}


@frappe.whitelist()
def publish_bom(bom_name, notes=None, ecn=None):
    """
    Publish a BOM using PLM version control (NOT ERPNext submit).
    - BOM stays docstatus=0 (always editable)
    - If current status is Draft: keep same version (unless v0 -> v1), change status to Published
    - If current status is Published: increment version, status stays Published
    - is_active=1 allows manufacturing use
    - ECN is required for all version changes
    """
    if not has_bom_publish_permission():
        frappe.throw(_("You don't have permission to publish BOMs"))
    
    # ECN is required
    if not ecn:
        frappe.throw(_("ECN is required to publish a BOM"))
    
    # Ensure tables exist
    ensure_bom_version_table()
    ensure_bom_custom_fields()
    
    bom = frappe.get_doc("BOM", bom_name)
    
    current_version = bom.get("current_version") or 0
    current_status = bom.get("plm_status") or "Draft"
    
    # Determine new version based on current status
    if current_status == "Published":
        # Published -> Publish: increment version
        new_version = current_version + 1
    elif current_version == 0:
        # First publish: v0 -> v1
        new_version = 1
    else:
        # Draft -> Publish: keep same version
        new_version = current_version
    
    # Create version snapshot
    bom_data = get_bom_snapshot(bom_name)
    
    # Check if version record already exists (for Draft -> Publish case)
    version_name = f"{bom_name}-v{new_version}"
    if frappe.db.exists("BOM Version", version_name):
        # Update existing version record
        frappe.db.set_value("BOM Version", version_name, {
            "status": "Published",
            "published_date": now_datetime(),
            "published_by": frappe.session.user,
            "bom_data": json.dumps(bom_data, default=str),
            "notes": notes or frappe.db.get_value("BOM Version", version_name, "notes"),
            "ecn": ecn
        })
    else:
        # Create new version record
        version_doc = frappe.get_doc({
            "doctype": "BOM Version",
            "bom": bom_name,
            "version": new_version,
            "status": "Published",
            "published_date": now_datetime(),
            "published_by": frappe.session.user,
            "bom_data": json.dumps(bom_data, default=str),
            "notes": notes,
            "ecn": ecn
        })
        version_doc.insert(ignore_permissions=True)
    
    # DO NOT submit the BOM - keep docstatus=0 so it stays editable
    # PLM uses plm_status + is_active to control manufacturing use
    
    # Update BOM - Published sets is_active=1, is_default=1 for manufacturing use
    frappe.db.set_value("BOM", bom_name, {
        "current_version": new_version,
        "plm_status": "Published",
        "bom_published_date": now_datetime(),
        "bom_published_by": frappe.session.user,
        "is_active": 1,
        "is_default": 1,
        "current_ecn": ecn
    }, update_modified=False)
    
    frappe.db.commit()
    
    return {
        "success": True,
        "message": _("Published as v{0}").format(new_version),
        "version": new_version
    }


@frappe.whitelist()
def block_bom(bom_name, notes=None):
    """
    Block a BOM.
    - Block does NOT increment version, only changes status to Blocked
    - Sets is_active=0 to prevent manufacturing use
    """
    if not has_bom_publish_permission():
        frappe.throw(_("You don't have permission to block BOMs"))
    
    # Ensure tables exist
    ensure_bom_version_table()
    ensure_bom_custom_fields()
    
    bom = frappe.get_doc("BOM", bom_name)
    
    current_version = bom.get("current_version") or 0
    
    # Block does NOT increment version
    new_version = current_version if current_version > 0 else 1
    
    # Create version snapshot
    bom_data = get_bom_snapshot(bom_name)
    
    # Check if version record already exists
    version_name = f"{bom_name}-v{new_version}"
    if frappe.db.exists("BOM Version", version_name):
        # Update existing version record to Blocked
        frappe.db.set_value("BOM Version", version_name, {
            "status": "Blocked",
            "published_date": now_datetime(),
            "published_by": frappe.session.user,
            "bom_data": json.dumps(bom_data, default=str),
            "notes": notes or _("BOM blocked")
        })
    else:
        # Create new version record (only if no version exists yet)
        version_doc = frappe.get_doc({
            "doctype": "BOM Version",
            "bom": bom_name,
            "version": new_version,
            "status": "Blocked",
            "published_date": now_datetime(),
            "published_by": frappe.session.user,
            "bom_data": json.dumps(bom_data, default=str),
            "notes": notes or _("BOM blocked")
        })
        version_doc.insert(ignore_permissions=True)
    
    # Update BOM - Block sets is_active=0, is_default=0 to prevent manufacturing use
    frappe.db.set_value("BOM", bom_name, {
        "current_version": new_version,
        "plm_status": "Blocked",
        "bom_published_date": now_datetime(),
        "bom_published_by": frappe.session.user,
        "is_active": 0,
        "is_default": 0
    }, update_modified=False)
    
    frappe.db.commit()
    
    return {
        "success": True,
        "message": _("BOM v{0} blocked").format(new_version),
        "version": new_version
    }


@frappe.whitelist()
def unblock_bom(bom_name):
    """
    Unblock a BOM - restores to Published status.
    - Sets is_active=1, is_default=1 to allow manufacturing use
    """
    if not has_bom_publish_permission():
        frappe.throw(_("You don't have permission to unblock BOMs"))
    
    ensure_bom_custom_fields()
    
    bom = frappe.get_doc("BOM", bom_name)
    current_version = bom.get("current_version") or 1
    
    # Update current version status if exists
    if frappe.db.exists("DocType", "BOM Version"):
        version_name = f"{bom_name}-v{current_version}"
        if frappe.db.exists("BOM Version", version_name):
            frappe.db.set_value("BOM Version", version_name, "status", "Published")
    
    # Update BOM - Unblock restores is_active=1, is_default=1 for manufacturing use
    frappe.db.set_value("BOM", bom_name, {
        "plm_status": "Published",
        "is_active": 1,
        "is_default": 1
    }, update_modified=False)
    frappe.db.commit()
    
    return {
        "success": True,
        "message": _("BOM has been unblocked")
    }


@frappe.whitelist()
def set_bom_as_draft(bom_name):
    """
    Set a BOM status to Draft - marks it as work-in-progress.
    Does not affect the version history.
    """
    if not has_bom_publish_permission():
        frappe.throw(_("You don't have permission to change BOM status"))
    
    ensure_bom_custom_fields()
    
    # Update BOM status to Draft
    frappe.db.set_value("BOM", bom_name, "plm_status", "Draft", update_modified=False)
    frappe.db.commit()
    
    return {
        "success": True,
        "message": _("BOM status set to Draft. You can continue editing and publish a new version when ready.")
    }


@frappe.whitelist()
def save_bom_as_draft(bom_name, notes=None, ecn=None):
    """
    Save a BOM as Draft.
    - If current status is Draft: keep same version, just update snapshot
    - If current status is Published: increment version, change to Draft
    - ECN is required for all version changes
    """
    if not has_bom_publish_permission():
        frappe.throw(_("You don't have permission to save versions"))
    
    # ECN is required
    if not ecn:
        frappe.throw(_("ECN is required to save as draft"))
    
    # Ensure tables exist
    ensure_bom_version_table()
    ensure_bom_custom_fields()
    
    bom = frappe.get_doc("BOM", bom_name)
    
    current_version = bom.get("current_version") or 0
    current_status = bom.get("plm_status") or "Draft"
    
    # Determine new version based on current status
    if current_status == "Published":
        # Published -> Draft: increment version
        new_version = current_version + 1
    else:
        # Draft -> Draft: keep same version
        new_version = current_version if current_version > 0 else 1
    
    # Create version snapshot
    bom_data = get_bom_snapshot(bom_name)
    
    # Check if version record already exists (for Draft -> Draft case)
    version_name = f"{bom_name}-v{new_version}"
    if frappe.db.exists("BOM Version", version_name):
        # Update existing version record
        frappe.db.set_value("BOM Version", version_name, {
            "status": "Draft",
            "published_date": now_datetime(),
            "published_by": frappe.session.user,
            "bom_data": json.dumps(bom_data, default=str),
            "notes": notes or frappe.db.get_value("BOM Version", version_name, "notes"),
            "ecn": ecn
        })
    else:
        # Create new version record
        version_doc = frappe.get_doc({
            "doctype": "BOM Version",
            "bom": bom_name,
            "version": new_version,
            "status": "Draft",
            "published_date": now_datetime(),
            "published_by": frappe.session.user,
            "bom_data": json.dumps(bom_data, default=str),
            "notes": notes or _("Saved as draft"),
            "ecn": ecn
        })
        version_doc.insert(ignore_permissions=True)
    
    # Update BOM - Draft sets is_default=0 (not used for manufacturing until published)
    frappe.db.set_value("BOM", bom_name, {
        "current_version": new_version,
        "plm_status": "Draft",
        "bom_published_date": now_datetime(),
        "bom_published_by": frappe.session.user,
        "is_active": 1,
        "is_default": 0,
        "current_ecn": ecn
    }, update_modified=False)
    
    frappe.db.commit()
    
    return {
        "success": True,
        "message": _("Saved as draft v{0}").format(new_version),
        "version": new_version
    }


@frappe.whitelist()
def convert_bom_to_plm_mode(bom_name):
    """
    Convert a submitted BOM (docstatus=1) to PLM mode (docstatus=0).
    This allows the BOM to be edited using PLM version control.
    The BOM remains active and usable for manufacturing.
    """
    if not has_bom_publish_permission():
        return {"success": False, "error": _("You don't have permission to convert BOMs")}
    
    try:
        bom = frappe.get_doc("BOM", bom_name)
        
        if bom.docstatus != 1:
            return {"success": False, "error": _("BOM is not submitted")}
        
        # Directly update docstatus to 0 (Draft) to make it editable
        # Keep is_active=1 so it can still be used for manufacturing
        frappe.db.set_value("BOM", bom_name, {
            "docstatus": 0,
            "is_active": 1
        }, update_modified=False)
        
        # Set PLM status to Published if not already set
        current_status = bom.get("plm_status")
        if not current_status or current_status == "Draft":
            frappe.db.set_value("BOM", bom_name, "plm_status", "Published", update_modified=False)
        
        frappe.db.commit()
        
        return {
            "success": True,
            "message": _("BOM converted to PLM mode. You can now edit it directly.")
        }
        
    except Exception as e:
        frappe.log_error(f"Error converting BOM to PLM mode: {str(e)}")
        return {"success": False, "error": str(e)}


@frappe.whitelist()
def delete_bom(bom_name):
    """
    Delete a BOM. If submitted, cancel first then delete.
    Also deletes related BOM Version records.
    """
    if not has_bom_publish_permission():
        return {"success": False, "error": _("You don't have permission to delete BOMs")}
    
    try:
        bom = frappe.get_doc("BOM", bom_name)
        
        # Check if BOM is linked to Work Orders
        work_orders = frappe.get_all("Work Order", filters={"bom_no": bom_name, "docstatus": ["!=", 2]}, limit=1)
        if work_orders:
            return {"success": False, "error": _("BOM is linked to Work Orders. Cancel/delete them first.")}
        
        # If submitted, cancel first
        if bom.docstatus == 1:
            bom.flags.ignore_permissions = True
            bom.cancel()
        
        # Delete BOM Version records
        if frappe.db.exists("DocType", "BOM Version"):
            frappe.db.delete("BOM Version", {"bom": bom_name})
        
        # Delete the BOM
        frappe.delete_doc("BOM", bom_name, force=True, ignore_permissions=True)
        frappe.db.commit()
        
        return {"success": True, "message": _("BOM {0} deleted").format(bom_name)}
        
    except Exception as e:
        frappe.log_error(f"Error deleting BOM: {str(e)}")
        return {"success": False, "error": str(e)}


@frappe.whitelist()
def bulk_delete_boms(bom_names):
    """
    Delete multiple BOMs.
    """
    import json
    if isinstance(bom_names, str):
        bom_names = json.loads(bom_names)
    
    results = {"deleted": [], "failed": []}
    
    for bom_name in bom_names:
        result = delete_bom(bom_name)
        if result.get("success"):
            results["deleted"].append(bom_name)
        else:
            results["failed"].append({"name": bom_name, "error": result.get("error")})
    
    return results


@frappe.whitelist()
def get_bom_version_history(bom_name):
    """
    Get all version history for a BOM.
    Includes ECN information.
    """
    if not frappe.db.exists("DocType", "BOM Version"):
        return []
    
    versions = frappe.get_all(
        "BOM Version",
        filters={"bom": bom_name},
        fields=["name", "version", "status", "published_date", "published_by", "notes", "ecn"],
        order_by="version desc"
    )
    
    # Get ECN info for display (name is the ECN number in format ECNXXXXXX)
    for v in versions:
        if v.ecn and frappe.db.exists("ECN", v.ecn):
            ecn_doc = frappe.get_doc("ECN", v.ecn)
            v["ecn_number"] = v.ecn  # name is the ECN number
            v["ecn_title"] = ecn_doc.title
        else:
            v["ecn_number"] = None
            v["ecn_title"] = None
    
    return versions


@frappe.whitelist()
def get_bom_version_data(version_name):
    """
    Get the snapshot data for a specific BOM version.
    """
    if not frappe.db.exists("BOM Version", version_name):
        return None
    
    version_doc = frappe.get_doc("BOM Version", version_name)
    if version_doc.bom_data:
        return json.loads(version_doc.bom_data)
    return None


@frappe.whitelist()
def restore_bom_version(bom_name, version_name):
    """
    Restore a BOM to a previous version.
    Creates a new version with the restored data.
    """
    if not has_bom_publish_permission():
        return {"success": False, "error": _("You don't have permission to restore versions")}
    
    if not frappe.db.exists("BOM Version", version_name):
        return {"success": False, "error": _("Version not found")}
    
    try:
        # Get the version data
        version_doc = frappe.get_doc("BOM Version", version_name)
        if not version_doc.bom_data:
            return {"success": False, "error": _("No data found in this version")}
        
        old_data = json.loads(version_doc.bom_data)
        
        # Get current BOM
        bom = frappe.get_doc("BOM", bom_name)
        
        # Fields to restore (exclude system fields and child tables that need special handling)
        exclude_fields = [
            'name', 'doctype', 'docstatus', 'idx', 'modified', 'creation', 
            'modified_by', 'owner', '_user_tags', '_comments', '_assign', '_liked_by',
            'current_version', 'plm_status', 'bom_published_date', 'bom_published_by'
        ]
        
        # Restore basic fields
        for key, value in old_data.items():
            if key not in exclude_fields and not isinstance(value, list):
                if hasattr(bom, key):
                    bom.set(key, value)
        
        # Handle child tables (like items, operations, etc.)
        child_tables = ['items', 'operations', 'scrap_items', 'exploded_items']
        
        for table_field in child_tables:
            if table_field in old_data and isinstance(old_data[table_field], list):
                # Clear existing rows
                bom.set(table_field, [])
                # Add rows from the version
                for row_data in old_data[table_field]:
                    # Remove system fields from row
                    for key in ['name', 'parent', 'parentfield', 'parenttype', 'idx', 'doctype']:
                        row_data.pop(key, None)
                    bom.append(table_field, row_data)
        
        # Save the BOM
        bom.flags.ignore_validate = True
        bom.flags.ignore_permissions = True
        bom.save()
        
        # Save as draft (not publish) so user can review before publishing
        result = save_bom_as_draft(bom_name, notes=_("Restored from version v{0}").format(version_doc.version))
        
        if result.get("success"):
            return {
                "success": True, 
                "message": _("Restored from v{0} as draft v{1}. Review and publish when ready.").format(
                    version_doc.version, result.get("version")
                )
            }
        else:
            return {"success": True, "message": _("Restored from v{0}").format(version_doc.version)}
            
    except Exception as e:
        frappe.log_error(f"Error restoring BOM version: {str(e)}")
        return {"success": False, "error": str(e)}


@frappe.whitelist()
def get_current_bom_version_ecn(bom_name):
    """
    Get the ECN of the current version for a BOM.
    Used to pre-fill the ECN field in the save dialog.
    """
    if not frappe.db.exists("BOM", bom_name):
        return None
    
    bom = frappe.get_doc("BOM", bom_name)
    current_version = bom.get("current_version") or 0
    current_status = bom.get("plm_status") or "Draft"
    
    # Only pre-fill for Draft status (same version will be updated)
    # For Published status, a new version will be created, so don't pre-fill
    if current_status != "Draft" or current_version == 0:
        return None
    
    # Get the ECN from the current version record
    version_name = f"{bom_name}-v{current_version}"
    if frappe.db.exists("BOM Version", version_name):
        ecn = frappe.db.get_value("BOM Version", version_name, "ecn")
        return ecn
    
    return None


@frappe.whitelist()
def compare_bom_versions(bom_name, version1, version2):
    """
    Compare two versions of a BOM.
    Returns the differences between versions.
    """
    version1_name = f"{bom_name}-v{version1}"
    version2_name = f"{bom_name}-v{version2}"
    
    if not frappe.db.exists("BOM Version", version1_name):
        return {"success": False, "error": _("Version {0} not found").format(version1)}
    
    if not frappe.db.exists("BOM Version", version2_name):
        return {"success": False, "error": _("Version {0} not found").format(version2)}
    
    data1 = get_bom_version_data(version1_name)
    data2 = get_bom_version_data(version2_name)
    
    if not data1 or not data2:
        return {"success": False, "error": _("Could not load version data")}
    
    differences = {
        "fields": [],
        "items_added": [],
        "items_removed": [],
        "items_changed": []
    }
    
    # Compare basic fields
    exclude_fields = ['modified', 'creation', 'modified_by', 'owner', '_user_tags', 
                      '_comments', '_assign', '_liked_by', 'items', 'operations', 
                      'scrap_items', 'exploded_items']
    
    for key in set(list(data1.keys()) + list(data2.keys())):
        if key in exclude_fields:
            continue
        val1 = data1.get(key)
        val2 = data2.get(key)
        if val1 != val2:
            differences["fields"].append({
                "field": key,
                "version1": val1,
                "version2": val2
            })
    
    # Compare items
    items1 = {item.get("item_code"): item for item in data1.get("items", [])}
    items2 = {item.get("item_code"): item for item in data2.get("items", [])}
    
    for item_code in set(list(items1.keys()) + list(items2.keys())):
        if item_code in items1 and item_code not in items2:
            differences["items_removed"].append(items1[item_code])
        elif item_code not in items1 and item_code in items2:
            differences["items_added"].append(items2[item_code])
        elif items1[item_code] != items2[item_code]:
            differences["items_changed"].append({
                "item_code": item_code,
                "version1": items1[item_code],
                "version2": items2[item_code]
            })
    
    return {
        "success": True,
        "differences": differences,
        "version1": version1,
        "version2": version2
    }
