import frappe
import json
from frappe import _
from frappe.utils import now_datetime


def ensure_work_order_custom_fields():
    """
    Create custom fields on Work Order for BOM version tracking.
    """
    fields_to_create = [
        {
            "dt": "Work Order",
            "fieldname": "bom_version",
            "label": "BOM Version",
            "fieldtype": "Int",
            "insert_after": "bom_no",
            "read_only": 1,
            "bold": 1,
            "description": "BOM version used for this Work Order"
        },
        {
            "dt": "Work Order",
            "fieldname": "bom_snapshot_data",
            "label": "BOM Snapshot Data",
            "fieldtype": "Long Text",
            "insert_after": "bom_version",
            "read_only": 1,
            "hidden": 1,
            "description": "Snapshot of BOM data at Work Order creation"
        },
        {
            "dt": "Work Order",
            "fieldname": "bom_plm_status_at_creation",
            "label": "BOM PLM Status at Creation",
            "fieldtype": "Data",
            "insert_after": "bom_snapshot_data",
            "read_only": 1,
            "hidden": 1
        }
    ]
    
    for field in fields_to_create:
        field_name = f"Work Order-{field['fieldname']}"
        if not frappe.db.exists("Custom Field", field_name):
            cf = frappe.get_doc({"doctype": "Custom Field", **field})
            cf.insert(ignore_permissions=True)
    
    frappe.db.commit()


@frappe.whitelist()
def setup_work_order_plm_fields():
    """
    Setup all required custom fields for Work Order PLM integration.
    """
    ensure_work_order_custom_fields()
    return {"success": True, "message": "Work Order PLM fields created successfully"}


def get_bom_version_snapshot(bom_name, version=None):
    """
    Get the BOM version snapshot data.
    If version is specified, get that version's snapshot.
    Otherwise, get the current published version.
    """
    if version:
        version_name = f"{bom_name}-v{version}"
        if frappe.db.exists("BOM Version", version_name):
            version_doc = frappe.get_doc("BOM Version", version_name)
            if version_doc.bom_data:
                return json.loads(version_doc.bom_data)
    
    # Get current BOM data as fallback
    bom = frappe.get_doc("BOM", bom_name)
    bom_data = bom.as_dict()
    
    # Clean up system fields
    for key in ['modified', 'creation', 'modified_by', 'owner', '_user_tags', '_comments', '_assign', '_liked_by']:
        bom_data.pop(key, None)
    
    return bom_data


def validate_bom_for_work_order(bom_name):
    """
    Validate that BOM is suitable for Work Order creation.
    Returns (is_valid, error_message, bom_version, bom_snapshot)
    """
    if not frappe.db.exists("BOM", bom_name):
        return False, _("BOM {0} does not exist").format(bom_name), None, None
    
    bom = frappe.get_doc("BOM", bom_name)
    
    # Check if BOM is submitted
    if bom.docstatus != 1:
        return False, _("BOM must be submitted before creating Work Order"), None, None
    
    # Check if BOM is active
    if not bom.is_active:
        return False, _("BOM is not active"), None, None
    
    # Check PLM status
    plm_status = bom.get("plm_status") or "Draft"
    
    if plm_status == "Blocked":
        return False, _("Cannot create Work Order for blocked BOM. BOM '{0}' is currently blocked.").format(bom_name), None, None
    
    if plm_status == "Draft":
        return False, _("Cannot create Work Order for draft BOM. Please publish BOM '{0}' first.").format(bom_name), None, None
    
    # Get current version
    current_version = bom.get("current_version") or 0
    
    if current_version == 0:
        return False, _("BOM has no published version. Please publish BOM '{0}' first.").format(bom_name), None, None
    
    # Get version snapshot
    bom_snapshot = get_bom_version_snapshot(bom_name, current_version)
    
    return True, None, current_version, bom_snapshot


def on_work_order_validate(doc, method):
    """
    Hook: Validate Work Order before save.
    Called via hooks.py doc_events.
    """
    if doc.is_new() and doc.bom_no:
        # Validate BOM status
        is_valid, error_msg, bom_version, bom_snapshot = validate_bom_for_work_order(doc.bom_no)
        
        if not is_valid:
            frappe.throw(error_msg)
        
        # Store version and snapshot
        doc.bom_version = bom_version
        doc.bom_snapshot_data = json.dumps(bom_snapshot, default=str)
        doc.bom_plm_status_at_creation = "Published"


def on_work_order_before_submit(doc, method):
    """
    Hook: Validate before submitting Work Order.
    Check if BOM is still valid (not blocked).
    """
    if doc.bom_no:
        bom = frappe.get_doc("BOM", doc.bom_no)
        plm_status = bom.get("plm_status") or "Draft"
        
        if plm_status == "Blocked":
            frappe.throw(
                _("Cannot submit Work Order. BOM '{0}' has been blocked. "
                  "Please contact your PLM administrator.").format(doc.bom_no)
            )


def check_bom_block_status(bom_name):
    """
    Check if BOM is blocked and return appropriate message.
    """
    if not frappe.db.exists("BOM", bom_name):
        return {"blocked": True, "message": _("BOM does not exist")}
    
    plm_status = frappe.db.get_value("BOM", bom_name, "plm_status")
    
    if plm_status == "Blocked":
        return {
            "blocked": True,
            "message": _("BOM '{0}' is blocked. Manufacturing operations are not allowed.").format(bom_name)
        }
    
    return {"blocked": False}


def on_job_card_validate(doc, method):
    """
    Hook: Validate Job Card before save.
    Check if associated BOM is blocked.
    """
    if doc.work_order:
        work_order = frappe.get_doc("Work Order", doc.work_order)
        if work_order.bom_no:
            status = check_bom_block_status(work_order.bom_no)
            if status["blocked"]:
                frappe.throw(status["message"])


def on_stock_entry_validate(doc, method):
    """
    Hook: Validate Stock Entry before save.
    Check if associated BOM is blocked for manufacturing entries.
    """
    if doc.work_order and doc.purpose in ["Manufacture", "Material Transfer for Manufacture"]:
        work_order = frappe.get_doc("Work Order", doc.work_order)
        if work_order.bom_no:
            status = check_bom_block_status(work_order.bom_no)
            if status["blocked"]:
                frappe.throw(status["message"])


@frappe.whitelist()
def get_work_order_bom_snapshot(work_order_name):
    """
    Get the BOM snapshot data stored in a Work Order.
    """
    if not frappe.db.exists("Work Order", work_order_name):
        return None
    
    snapshot_data = frappe.db.get_value("Work Order", work_order_name, "bom_snapshot_data")
    
    if snapshot_data:
        return json.loads(snapshot_data)
    
    return None


@frappe.whitelist()
def get_work_order_items_from_snapshot(work_order_name):
    """
    Get BOM items from the Work Order's snapshot instead of live BOM.
    This ensures Work Order uses the version that was current at creation.
    """
    snapshot = get_work_order_bom_snapshot(work_order_name)
    
    if snapshot and "items" in snapshot:
        return snapshot["items"]
    
    # Fallback to live BOM data
    work_order = frappe.get_doc("Work Order", work_order_name)
    if work_order.bom_no:
        bom = frappe.get_doc("BOM", work_order.bom_no)
        return [item.as_dict() for item in bom.items]
    
    return []


def override_work_order_get_items(doc):
    """
    Override the standard get_items method to use snapshot data.
    This is called when Work Order fetches BOM items.
    """
    if doc.bom_snapshot_data:
        try:
            snapshot = json.loads(doc.bom_snapshot_data)
            if "items" in snapshot:
                return snapshot["items"]
        except:
            pass
    
    return None


@frappe.whitelist()
def check_bom_status_for_operation(work_order_name):
    """
    API to check if manufacturing operations can proceed.
    Called from frontend before operations.
    """
    if not frappe.db.exists("Work Order", work_order_name):
        return {"can_proceed": False, "error": _("Work Order not found")}
    
    work_order = frappe.get_doc("Work Order", work_order_name)
    
    if not work_order.bom_no:
        return {"can_proceed": True}
    
    status = check_bom_block_status(work_order.bom_no)
    
    if status["blocked"]:
        return {
            "can_proceed": False,
            "error": status["message"],
            "bom_blocked": True
        }
    
    return {
        "can_proceed": True,
        "bom_version": work_order.bom_version,
        "current_bom_version": frappe.db.get_value("BOM", work_order.bom_no, "current_version")
    }
