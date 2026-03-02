import frappe
import os
from frappe import _


def validate_document(doc, method):
    """
    Validate Document - require attachment and auto-populate filename.
    """
    # Allow "pending_upload" placeholder for new documents (file will be uploaded after save)
    if doc.attachment == "pending_upload":
        # This is a new document with pending file upload
        # Skip attachment validation - file will be uploaded after save
        return
    
    # Require attachment (validated in code instead of field level to prevent auto-save)
    if not doc.attachment:
        frappe.throw(frappe._("Attachment is required"))
    
    # Keep original filename if already set (user-selected name); otherwise use attachment basename.
    # Frappe appends a suffix (e.g. a88096) to uploaded files to avoid collisions, so we avoid
    # overwriting the user's filename with the suffixed one.
    if not doc.filename:
        doc.filename = os.path.basename(doc.attachment)


def after_insert_document(doc, method):
    """
    After inserting a Document, automatically add it to the linked Item's
    custom_document_list child table (Item Drawing Link) if the item field is set.
    """
    if not doc.item:
        return

    item_doc = frappe.get_doc("Item", doc.item)

    # Check if already linked to avoid duplicates
    already_linked = any(row.link == doc.name for row in (item_doc.custom_document_list or []))
    if already_linked:
        return

    item_doc.append("custom_document_list", {"link": doc.name})
    item_doc.save(ignore_permissions=True)
    frappe.db.commit()


def before_cancel_document(doc, method):
    """
    Before cancelling a Document, set flag to ignore linked documents check.
    This allows the Document to be cancelled even when linked to Items.
    """
    # Set flag to ignore linked documents validation
    doc.flags.ignore_links = True


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def item_query(doctype, txt, searchfield, start, page_len, filters):
    """Return Items ordered by creation DESC (newest first) for all Item link fields."""
    meta = frappe.get_meta("Item")
    valid_fields = {f.fieldname for f in meta.fields} | {
        "name", "owner", "creation", "modified", "docstatus", "disabled",
    }

    filter_conditions = ""
    if filters:
        if isinstance(filters, str):
            filters = frappe.parse_json(filters)
        if isinstance(filters, dict):
            for key, value in filters.items():
                if key in valid_fields:
                    filter_conditions += " AND `tabItem`.`{0}` = {1}".format(
                        key, frappe.db.escape(value)
                    )

    return frappe.db.sql(
        """
        SELECT `tabItem`.name, `tabItem`.item_name, `tabItem`.item_group
        FROM `tabItem`
        WHERE (`tabItem`.`{key}` LIKE %(txt)s
            OR `tabItem`.item_name LIKE %(txt)s
            OR `tabItem`.item_group LIKE %(txt)s)
            {filter_conditions}
        ORDER BY `tabItem`.creation DESC
        LIMIT %(page_len)s OFFSET %(start)s
        """.format(key=searchfield, filter_conditions=filter_conditions),
        {"txt": "%{0}%".format(txt), "start": start, "page_len": page_len},
    )


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_submitted_documents(doctype, txt, searchfield, start, page_len, filters):
    """Return submitted Documents ordered by creation DESC (newest first)."""
    return frappe.db.sql(
        """
        SELECT `tabDocument`.name, `tabDocument`.type, `tabDocument`.description
        FROM `tabDocument`
        WHERE `tabDocument`.docstatus = 1
            AND (`tabDocument`.{key} LIKE %(txt)s
                OR `tabDocument`.description LIKE %(txt)s
                OR `tabDocument`.type LIKE %(txt)s)
        ORDER BY `tabDocument`.creation DESC
        LIMIT %(page_len)s OFFSET %(start)s
        """.format(key=searchfield),
        {"txt": "%{0}%".format(txt), "start": start, "page_len": page_len},
    )


def on_cancel_document(doc, method):
    """
    After cancelling a Document, remove references from Item Drawing Link child table.
    """
    # Find all Item Drawing Link entries that reference this Document
    linked_items = frappe.get_all(
        "Item Drawing Link",
        filters={"link": doc.name},
        fields=["name", "parent", "parenttype"]
    )
    
    if linked_items:
        for link in linked_items:
            # Delete the Item Drawing Link entry
            frappe.delete_doc("Item Drawing Link", link.name, ignore_permissions=True, force=True)
            
            frappe.msgprint(
                f"Removed link to Document from {link.parenttype} {link.parent}",
                alert=True
            )
