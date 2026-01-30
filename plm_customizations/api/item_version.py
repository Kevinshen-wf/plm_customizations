import frappe
import json
from frappe import _
from frappe.utils import now_datetime


def get_document_snapshot(item_code):
    """
    Get a snapshot of all documents attached to an Item.
    Returns a list of document data that can be stored in Item Version.
    """
    documents = frappe.get_all(
        "Item Drawing Link",
        filters={"parent": item_code, "parenttype": "Item"},
        fields=["name", "link", "version", "type"]
    )
    
    snapshot = []
    for doc in documents:
        # Get the Document record to get attachment info
        if doc.link and frappe.db.exists("Document", doc.link):
            doc_record = frappe.get_doc("Document", doc.link)
            snapshot.append({
                "link": doc.link,
                "version": doc.version,
                "type": doc.type,
                "attachment": doc_record.get("attachment"),
                "filename": doc_record.get("filename") or doc_record.get("attachment")
            })
    
    return snapshot


def ensure_item_version_table():
    """
    Create Item Version table if it doesn't exist.
    Uses Custom DocType created via Frappe.
    """
    if not frappe.db.exists("DocType", "Item Version"):
        # Create the DocType programmatically
        doc = frappe.get_doc({
            "doctype": "DocType",
            "name": "Item Version",
            "module": "Stock",
            "custom": 1,
            "autoname": "format:{item_code}-v{version}",
            "naming_rule": "Expression",
            "fields": [
                {"fieldname": "item_code", "label": "Item Code", "fieldtype": "Link", "options": "Item", "reqd": 1, "in_list_view": 1},
                {"fieldname": "version", "label": "Version", "fieldtype": "Int", "reqd": 1, "in_list_view": 1, "read_only": 1},
                {"fieldname": "status", "label": "Status", "fieldtype": "Select", "options": "Draft\nPublished\nBlocked", "default": "Draft", "in_list_view": 1},
                {"fieldname": "column_break_1", "fieldtype": "Column Break"},
                {"fieldname": "published_date", "label": "Published Date", "fieldtype": "Datetime", "read_only": 1},
                {"fieldname": "published_by", "label": "Published By", "fieldtype": "Link", "options": "User", "read_only": 1},
                {"fieldname": "section_break_snapshot", "label": "Version Snapshot", "fieldtype": "Section Break"},
                {"fieldname": "item_data", "label": "Item Data (JSON)", "fieldtype": "Long Text", "read_only": 1, "hidden": 1},
                {"fieldname": "notes", "label": "Version Notes", "fieldtype": "Text"}
            ],
            "permissions": [
                {"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1},
                {"role": "Item Manager", "read": 1, "write": 1, "create": 1},
                {"role": "Stock User", "read": 1}
            ]
        })
        doc.insert(ignore_permissions=True)
        frappe.db.commit()


def ensure_item_custom_fields():
    """
    Create custom fields on Item if they don't exist.
    """
    fields_to_create = [
        {"dt": "Item", "fieldname": "current_version", "label": "Current Version", "fieldtype": "Int", 
         "insert_after": "naming_series", "default": "0", "read_only": 1, "bold": 1},
        {"dt": "Item", "fieldname": "plm_status", "label": "PLM Status", "fieldtype": "Select",
         "options": "Draft\nPublished\nBlocked", "insert_after": "current_version", "default": "Draft", "read_only": 1},
        {"dt": "Item", "fieldname": "published_date", "label": "Published Date", "fieldtype": "Datetime",
         "insert_after": "plm_status", "read_only": 1},
        {"dt": "Item", "fieldname": "published_by", "label": "Published By", "fieldtype": "Link",
         "options": "User", "insert_after": "published_date", "read_only": 1}
    ]
    
    for field in fields_to_create:
        field_name = f"Item-{field['fieldname']}"
        if not frappe.db.exists("Custom Field", field_name):
            cf = frappe.get_doc({"doctype": "Custom Field", **field})
            cf.insert(ignore_permissions=True)
    
    frappe.db.commit()


@frappe.whitelist()
def setup_plm_fields():
    """
    Setup all required fields and DocTypes for PLM version control.
    Call this once to initialize the system.
    """
    ensure_item_custom_fields()
    ensure_item_version_table()
    return {"success": True, "message": "PLM fields and DocTypes created successfully"}


@frappe.whitelist()
def publish_item(item_code, notes=None, ecn=None):
    """
    Publish an Item.
    - If current status is Draft: keep same version (unless v0 -> v1), change status to Published
    - If current status is Published: increment version, status stays Published
    - ECN is required for all version changes
    """
    if not has_publish_permission():
        frappe.throw(_("You don't have permission to publish items"))
    
    # ECN is required
    if not ecn:
        frappe.throw(_("ECN is required to publish an item"))
    
    # Ensure tables exist
    ensure_item_version_table()
    ensure_item_custom_fields()
    
    item = frappe.get_doc("Item", item_code)
    
    current_version = item.get("current_version") or 0
    current_status = item.get("plm_status") or "Draft"
    
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
    item_data = item.as_dict()
    for key in ['modified', 'creation', 'modified_by', 'owner', '_user_tags', '_comments', '_assign', '_liked_by']:
        item_data.pop(key, None)
    
    # Capture document snapshot
    document_snapshot = get_document_snapshot(item_code)
    
    # Check if version record already exists (for Draft -> Publish case)
    version_name = f"{item_code}-v{new_version}"
    if frappe.db.exists("Item Version", version_name):
        # Update existing version record
        frappe.db.set_value("Item Version", version_name, {
            "status": "Published",
            "published_date": now_datetime(),
            "published_by": frappe.session.user,
            "item_data": json.dumps(item_data, default=str),
            "document_snapshot": json.dumps(document_snapshot, default=str),
            "notes": notes or frappe.db.get_value("Item Version", version_name, "notes"),
            "ecn": ecn
        })
    else:
        # Create new version record
        version_doc = frappe.get_doc({
            "doctype": "Item Version",
            "item_code": item_code,
            "version": new_version,
            "status": "Published",
            "published_date": now_datetime(),
            "published_by": frappe.session.user,
            "item_data": json.dumps(item_data, default=str),
            "document_snapshot": json.dumps(document_snapshot, default=str),
            "notes": notes,
            "ecn": ecn
        })
        version_doc.insert(ignore_permissions=True)
    
    # Update Item
    frappe.db.set_value("Item", item_code, {
        "current_version": new_version,
        "plm_status": "Published",
        "published_date": now_datetime(),
        "published_by": frappe.session.user,
        "current_ecn": ecn
    }, update_modified=False)
    
    frappe.db.commit()
    
    return {
        "success": True,
        "message": _("Published as v{0}").format(new_version),
        "version": new_version
    }


@frappe.whitelist()
def block_item(item_code, notes=None):
    """
    Block an Item.
    - Block does NOT increment version, only changes status to Blocked
    - Updates existing version record to Blocked status
    """
    if not has_publish_permission():
        frappe.throw(_("You don't have permission to block items"))
    
    # Ensure tables exist
    ensure_item_version_table()
    ensure_item_custom_fields()
    
    item = frappe.get_doc("Item", item_code)
    
    current_version = item.get("current_version") or 0
    
    # Block does NOT increment version
    new_version = current_version if current_version > 0 else 1
    
    # Create version snapshot
    item_data = item.as_dict()
    for key in ['modified', 'creation', 'modified_by', 'owner', '_user_tags', '_comments', '_assign', '_liked_by']:
        item_data.pop(key, None)
    
    # Capture document snapshot
    document_snapshot = get_document_snapshot(item_code)
    
    # Check if version record already exists
    version_name = f"{item_code}-v{new_version}"
    if frappe.db.exists("Item Version", version_name):
        # Update existing version record to Blocked
        frappe.db.set_value("Item Version", version_name, {
            "status": "Blocked",
            "published_date": now_datetime(),
            "published_by": frappe.session.user,
            "item_data": json.dumps(item_data, default=str),
            "document_snapshot": json.dumps(document_snapshot, default=str),
            "notes": notes or _("Item blocked")
        })
    else:
        # Create new version record (only if no version exists yet)
        version_doc = frappe.get_doc({
            "doctype": "Item Version",
            "item_code": item_code,
            "version": new_version,
            "status": "Blocked",
            "published_date": now_datetime(),
            "published_by": frappe.session.user,
            "item_data": json.dumps(item_data, default=str),
            "document_snapshot": json.dumps(document_snapshot, default=str),
            "notes": notes or _("Item blocked")
        })
        version_doc.insert(ignore_permissions=True)
    
    # Update Item - version stays the same, only status changes
    frappe.db.set_value("Item", item_code, {
        "current_version": new_version,
        "plm_status": "Blocked",
        "published_date": now_datetime(),
        "published_by": frappe.session.user
    }, update_modified=False)
    
    frappe.db.commit()
    
    return {
        "success": True,
        "message": _("Item v{0} blocked").format(new_version),
        "version": new_version
    }


@frappe.whitelist()
def unblock_item(item_code):
    """
    Unblock an Item - restores to Published status.
    """
    if not has_publish_permission():
        frappe.throw(_("You don't have permission to unblock items"))
    
    ensure_item_custom_fields()
    
    item = frappe.get_doc("Item", item_code)
    current_version = item.get("current_version") or 1
    
    # Update current version status if exists
    if frappe.db.exists("DocType", "Item Version"):
        version_name = f"{item_code}-v{current_version}"
        if frappe.db.exists("Item Version", version_name):
            frappe.db.set_value("Item Version", version_name, "status", "Published")
    
    # Update Item
    frappe.db.set_value("Item", item_code, "plm_status", "Published", update_modified=False)
    frappe.db.commit()
    
    return {
        "success": True,
        "message": _("Item has been unblocked")
    }


@frappe.whitelist()
def set_as_draft(item_code):
    """
    Set an Item status to Draft - marks it as work-in-progress.
    Does not affect the version history.
    """
    if not has_publish_permission():
        frappe.throw(_("You don't have permission to change item status"))
    
    ensure_item_custom_fields()
    
    # Update Item status to Draft
    frappe.db.set_value("Item", item_code, "plm_status", "Draft", update_modified=False)
    frappe.db.commit()
    
    return {
        "success": True,
        "message": _("Item status set to Draft. You can continue editing and publish a new version when ready.")
    }


@frappe.whitelist()
def save_as_draft(item_code, notes=None, ecn=None):
    """
    Save an Item as Draft.
    - If current status is Draft: keep same version, just update snapshot
    - If current status is Published: increment version, change to Draft
    - ECN is required for all version changes
    """
    if not has_publish_permission():
        frappe.throw(_("You don't have permission to save versions"))
    
    # ECN is required
    if not ecn:
        frappe.throw(_("ECN is required to save as draft"))
    
    # Ensure tables exist
    ensure_item_version_table()
    ensure_item_custom_fields()
    
    item = frappe.get_doc("Item", item_code)
    
    current_version = item.get("current_version") or 0
    current_status = item.get("plm_status") or "Draft"
    
    # Determine new version based on current status
    if current_status == "Published":
        # Published -> Draft: increment version
        new_version = current_version + 1
    else:
        # Draft -> Draft: keep same version
        new_version = current_version if current_version > 0 else 1
    
    # Create version snapshot
    item_data = item.as_dict()
    for key in ['modified', 'creation', 'modified_by', 'owner', '_user_tags', '_comments', '_assign', '_liked_by']:
        item_data.pop(key, None)
    
    # Capture document snapshot
    document_snapshot = get_document_snapshot(item_code)
    
    # Check if version record already exists (for Draft -> Draft case)
    version_name = f"{item_code}-v{new_version}"
    if frappe.db.exists("Item Version", version_name):
        # Update existing version record
        frappe.db.set_value("Item Version", version_name, {
            "status": "Draft",
            "published_date": now_datetime(),
            "published_by": frappe.session.user,
            "item_data": json.dumps(item_data, default=str),
            "document_snapshot": json.dumps(document_snapshot, default=str),
            "notes": notes or frappe.db.get_value("Item Version", version_name, "notes"),
            "ecn": ecn
        })
    else:
        # Create new version record
        version_doc = frappe.get_doc({
            "doctype": "Item Version",
            "item_code": item_code,
            "version": new_version,
            "status": "Draft",
            "published_date": now_datetime(),
            "published_by": frappe.session.user,
            "item_data": json.dumps(item_data, default=str),
            "document_snapshot": json.dumps(document_snapshot, default=str),
            "notes": notes or _("Saved as draft"),
            "ecn": ecn
        })
        version_doc.insert(ignore_permissions=True)
    
    # Update Item
    frappe.db.set_value("Item", item_code, {
        "current_version": new_version,
        "plm_status": "Draft",
        "published_date": now_datetime(),
        "published_by": frappe.session.user,
        "current_ecn": ecn
    }, update_modified=False)
    
    frappe.db.commit()
    
    return {
        "success": True,
        "message": _("Saved as draft v{0}").format(new_version),
        "version": new_version
    }


@frappe.whitelist()
def get_version_history(item_code):
    """
    Get all version history for an Item.
    Includes ECN information.
    """
    if not frappe.db.exists("DocType", "Item Version"):
        return []
    
    versions = frappe.get_all(
        "Item Version",
        filters={"item_code": item_code},
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
def get_version_data(version_name):
    """
    Get the snapshot data for a specific version.
    """
    if not frappe.db.exists("Item Version", version_name):
        return None
    
    version_doc = frappe.get_doc("Item Version", version_name)
    if version_doc.item_data:
        return json.loads(version_doc.item_data)
    return None


@frappe.whitelist()
def can_view_item(item_code):
    """
    Check if current user can view the item.
    Viewers can only see Published items.
    """
    if has_publish_permission():
        return True
    
    item = frappe.get_doc("Item", item_code)
    status = item.get("plm_status") or "Draft"
    
    # Viewers can only see Published items
    return status == "Published"


@frappe.whitelist()
def can_download_documents(item_code):
    """
    Check if documents can be downloaded.
    Returns False if item is Blocked.
    """
    item = frappe.get_doc("Item", item_code)
    status = item.get("plm_status") or "Draft"
    
    if status == "Blocked":
        return {"can_download": False, "reason": "Item is blocked"}
    
    # For viewers, only published items
    if not has_publish_permission() and status != "Published":
        return {"can_download": False, "reason": "Item is not published"}
    
    return {"can_download": True}


@frappe.whitelist()
def has_publish_permission():
    """
    Check if user has permission to publish/block items.
    """
    user_roles = frappe.get_roles(frappe.session.user)
    allowed_roles = ["System Manager", "Item Manager", "Stock Manager", "Mechanical Engineer"]
    return any(role in user_roles for role in allowed_roles)


@frappe.whitelist()
def restore_version(item_code, version_name):
    """
    Restore an Item to a previous version.
    Creates a new version with the restored data.
    """
    if not has_publish_permission():
        return {"success": False, "error": _("You don't have permission to restore versions")}
    
    if not frappe.db.exists("Item Version", version_name):
        return {"success": False, "error": _("Version not found")}
    
    try:
        # Get the version data
        version_doc = frappe.get_doc("Item Version", version_name)
        if not version_doc.item_data:
            return {"success": False, "error": _("No data found in this version")}
        
        old_data = json.loads(version_doc.item_data)
        
        # Get current item
        item = frappe.get_doc("Item", item_code)
        
        # Fields to restore (exclude system fields and child tables that need special handling)
        exclude_fields = [
            'name', 'doctype', 'docstatus', 'idx', 'modified', 'creation', 
            'modified_by', 'owner', '_user_tags', '_comments', '_assign', '_liked_by',
            'current_version', 'plm_status', 'published_date', 'published_by'
        ]
        
        # Restore basic fields
        for key, value in old_data.items():
            if key not in exclude_fields and not isinstance(value, list):
                if hasattr(item, key):
                    item.set(key, value)
        
        # Handle child tables (like custom_document_list)
        child_tables = ['custom_document_list', 'uoms', 'barcodes', 'reorder_levels', 
                        'attributes', 'supplier_items', 'customer_items', 'taxes', 'item_defaults']
        
        for table_field in child_tables:
            if table_field in old_data and isinstance(old_data[table_field], list):
                # Clear existing rows
                item.set(table_field, [])
                # Add rows from the version
                for row_data in old_data[table_field]:
                    # Remove system fields from row
                    for key in ['name', 'parent', 'parentfield', 'parenttype', 'idx', 'doctype']:
                        row_data.pop(key, None)
                    item.append(table_field, row_data)
        
        # Save the item
        item.flags.ignore_validate = True
        item.flags.ignore_permissions = True
        item.save()
        
        # Save as draft (not publish) so user can review before publishing
        result = save_as_draft(item_code, notes=_("Restored from version v{0}").format(version_doc.version))
        
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
        frappe.log_error(f"Error restoring version: {str(e)}")
        return {"success": False, "error": str(e)}


@frappe.whitelist()
def get_downloadable_versions(item_code):
    """
    Get list of versions available for download.
    Returns versions with document snapshots.
    """
    if not frappe.db.exists("Item", item_code):
        return {"versions": []}
    
    item = frappe.get_doc("Item", item_code)
    current_version = item.get("current_version") or 0
    current_status = item.get("plm_status") or "Draft"
    
    versions = []
    
    # Add current version option
    current_docs = get_document_snapshot(item_code)
    versions.append({
        "version": current_version,
        "version_name": f"{item_code}-v{current_version}",
        "label": f"v{current_version} - Current ({current_status})",
        "status": current_status,
        "is_current": True,
        "document_count": len(current_docs),
        "has_snapshot": True
    })
    
    # Get historical versions with document snapshots
    if frappe.db.exists("DocType", "Item Version"):
        historical = frappe.get_all(
            "Item Version",
            filters={"item_code": item_code},
            fields=["name", "version", "status", "published_date", "document_snapshot"],
            order_by="version desc"
        )
        
        for v in historical:
            if v.version == current_version:
                continue  # Skip current version as it's already added
            
            doc_count = 0
            has_snapshot = False
            if v.document_snapshot:
                try:
                    docs = json.loads(v.document_snapshot)
                    doc_count = len(docs) if isinstance(docs, list) else 0
                    has_snapshot = doc_count > 0
                except:
                    pass
            
            # Only include versions with snapshots
            if has_snapshot:
                versions.append({
                    "version": v.version,
                    "version_name": v.name,
                    "label": f"v{v.version} - {v.status}",
                    "status": v.status,
                    "is_current": False,
                    "document_count": doc_count,
                    "has_snapshot": has_snapshot,
                    "published_date": str(v.published_date) if v.published_date else None
                })
    
    return {"versions": versions}


@frappe.whitelist()
def get_version_documents(item_code, version=None):
    """
    Get documents for a specific version.
    If version is None or 'current', returns current documents.
    Otherwise returns documents from the version snapshot.
    """
    if not version or version == "current":
        # Return current documents
        documents = get_document_snapshot(item_code)
        return {"documents": documents, "version": "current"}
    
    # Get documents from version snapshot
    version_name = f"{item_code}-v{version}"
    if not frappe.db.exists("Item Version", version_name):
        return {"documents": [], "error": "Version not found"}
    
    version_doc = frappe.get_doc("Item Version", version_name)
    
    if not version_doc.document_snapshot:
        return {"documents": [], "error": "No document snapshot for this version"}
    
    try:
        documents = json.loads(version_doc.document_snapshot)
        return {"documents": documents, "version": version}
    except:
        return {"documents": [], "error": "Failed to parse document snapshot"}


@frappe.whitelist()
def get_current_version_ecn(item_code):
    """
    Get the ECN of the current version for an Item.
    Used to pre-fill the ECN field in the save dialog.
    """
    if not frappe.db.exists("Item", item_code):
        return None
    
    item = frappe.get_doc("Item", item_code)
    current_version = item.get("current_version") or 0
    current_status = item.get("plm_status") or "Draft"
    
    # Only pre-fill for Draft status (same version will be updated)
    # For Published status, a new version will be created, so don't pre-fill
    if current_status != "Draft" or current_version == 0:
        return None
    
    # Get the ECN from the current version record
    version_name = f"{item_code}-v{current_version}"
    if frappe.db.exists("Item Version", version_name):
        ecn = frappe.db.get_value("Item Version", version_name, "ecn")
        return ecn
    
    return None


@frappe.whitelist()
def compare_versions(item_code, version1, version2):
    """
    Compare two versions of an Item.
    Returns the differences between versions.
    """
    version1_name = f"{item_code}-v{version1}"
    version2_name = f"{item_code}-v{version2}"
    
    if not frappe.db.exists("Item Version", version1_name):
        return {"success": False, "error": _("Version {0} not found").format(version1)}
    
    if not frappe.db.exists("Item Version", version2_name):
        return {"success": False, "error": _("Version {0} not found").format(version2)}
    
    data1 = get_version_data(version1_name)
    data2 = get_version_data(version2_name)
    
    if not data1 or not data2:
        return {"success": False, "error": _("Could not load version data")}
    
    differences = {
        "fields": [],
        "documents_added": [],
        "documents_removed": [],
        "documents_changed": []
    }
    
    # Compare basic fields
    exclude_fields = ['modified', 'creation', 'modified_by', 'owner', '_user_tags', 
                      '_comments', '_assign', '_liked_by', 'custom_document_list',
                      'uoms', 'barcodes', 'reorder_levels', 'attributes', 
                      'supplier_items', 'customer_items', 'taxes', 'item_defaults']
    
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
    
    # Compare document list
    docs1 = {doc.get("link"): doc for doc in data1.get("custom_document_list", []) if doc.get("link")}
    docs2 = {doc.get("link"): doc for doc in data2.get("custom_document_list", []) if doc.get("link")}
    
    for doc_link in set(list(docs1.keys()) + list(docs2.keys())):
        if doc_link in docs1 and doc_link not in docs2:
            differences["documents_removed"].append(docs1[doc_link])
        elif doc_link not in docs1 and doc_link in docs2:
            differences["documents_added"].append(docs2[doc_link])
        elif docs1.get(doc_link) != docs2.get(doc_link):
            differences["documents_changed"].append({
                "link": doc_link,
                "version1": docs1.get(doc_link),
                "version2": docs2.get(doc_link)
            })
    
    return {
        "success": True,
        "differences": differences,
        "version1": version1,
        "version2": version2
    }
