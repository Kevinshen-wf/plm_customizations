import frappe
import os


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


def before_cancel_document(doc, method):
    """
    Before cancelling a Document, set flag to ignore linked documents check.
    This allows the Document to be cancelled even when linked to Items.
    """
    # Set flag to ignore linked documents validation
    doc.flags.ignore_links = True


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
