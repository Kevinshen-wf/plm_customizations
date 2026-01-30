# Copyright (c) 2024, PLM Customizations and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


class ECN(Document):
    def before_insert(self):
        """Set author and creation_date automatically on creation."""
        if not self.author:
            self.author = frappe.session.user
        if not self.creation_date:
            self.creation_date = now_datetime()

    def before_save(self):
        """Ensure author and creation_date are set."""
        if not self.author:
            self.author = frappe.session.user
        if not self.creation_date:
            self.creation_date = now_datetime()


@frappe.whitelist()
def get_linked_versions(ecn_name):
    """
    Get all Item Versions and BOM Versions linked to this ECN.
    """
    result = {
        "item_versions": [],
        "bom_versions": []
    }
    
    # Get linked Item Versions
    if frappe.db.exists("DocType", "Item Version"):
        item_versions = frappe.get_all(
            "Item Version",
            filters={"ecn": ecn_name},
            fields=["name", "item_code", "version", "status", "published_date"]
        )
        result["item_versions"] = item_versions
    
    # Get linked BOM Versions
    if frappe.db.exists("DocType", "BOM Version"):
        bom_versions = frappe.get_all(
            "BOM Version",
            filters={"ecn": ecn_name},
            fields=["name", "bom", "version", "status", "published_date"]
        )
        result["bom_versions"] = bom_versions
    
    return result
