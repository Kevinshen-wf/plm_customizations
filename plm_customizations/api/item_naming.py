import frappe
from frappe import _


# Category mappings
CATEGORY1_MAP = {
    "E - Electrical/Electronic": "E",
    "M - Mechanical": "M",
    "P - Packaging/Panel": "P",
    "C - Consumable": "C",
    "S - Software/Specification": "S"
}

CATEGORY2_MAP = {
    "STD - Standard Part": "STD",
    "CAT - Purchased Part": "CAT",
    "CUS - Custom Part": "CUS",
    "ASM - Assembly": "ASM"
}


def get_category_code(category1, category2):
    """Get the category codes from full names"""
    cat1_code = CATEGORY1_MAP.get(category1, "")
    cat2_code = CATEGORY2_MAP.get(category2, "")
    return cat1_code, cat2_code


def get_next_sequence(cat1_code, cat2_code):
    """Get the next sequence number for the given category combination"""
    prefix = f"{cat1_code}-{cat2_code}-"
    
    # Find the highest existing sequence for this prefix
    existing = frappe.db.sql("""
        SELECT item_code FROM `tabItem` 
        WHERE item_code LIKE %s
        ORDER BY item_code DESC
        LIMIT 1
    """, (f"{prefix}%",), as_dict=True)
    
    if existing:
        # Extract the sequence number from the last item code
        last_code = existing[0].item_code
        try:
            # Format: E-STD-0001_V01 or E-STD-0001
            # Extract the number part
            parts = last_code.replace(prefix, "").split("_")[0]
            last_seq = int(parts)
            return last_seq + 1
        except (ValueError, IndexError):
            return 1
    
    return 1


@frappe.whitelist()
def generate_item_code(category1, category2, include_version=False, version=None):
    """
    Generate an item code based on categories.
    Format: Category1-Category2-XXXX or Category1-Category2-XXXX_V00
    
    Args:
        category1: Full category1 name (e.g., "E - Electrical/Electronic")
        category2: Full category2 name (e.g., "STD - Standard Part")
        include_version: Whether to include version suffix
        version: Version number (default: 0)
    
    Returns:
        Generated item code
    """
    cat1_code, cat2_code = get_category_code(category1, category2)
    
    if not cat1_code or not cat2_code:
        frappe.throw(_("Please select both Category 1 and Category 2"))
    
    # Get next sequence number
    seq = get_next_sequence(cat1_code, cat2_code)
    
    # Format: E-STD-0001
    item_code = f"{cat1_code}-{cat2_code}-{seq:04d}"
    
    # Add version suffix if requested
    if include_version:
        ver = version if version is not None else 0
        item_code = f"{item_code}_V{ver:02d}"
    
    return item_code


@frappe.whitelist()
def preview_item_code(category1, category2):
    """
    Preview the next item code that would be generated.
    """
    if not category1 or not category2:
        return ""
    
    return generate_item_code(category1, category2, include_version=False)


def before_insert_item(doc, method):
    """
    Hook to auto-generate item code before insert if use_auto_naming is checked.
    """
    if doc.get("use_auto_naming") and doc.get("category1") and doc.get("category2"):
        # Generate the item code
        new_code = generate_item_code(doc.category1, doc.category2, include_version=False)
        doc.item_code = new_code
        doc.item_name = doc.item_name or new_code
        
        # Sync item_group with categories
        sync_item_group_with_categories(doc)


def validate_item(doc, method):
    """
    Validate item before save.
    """
    # If using auto naming, ensure categories are set
    if doc.get("use_auto_naming"):
        if not doc.get("category1"):
            frappe.throw(_("Category 1 is required when using auto-naming"))
        if not doc.get("category2"):
            frappe.throw(_("Category 2 is required when using auto-naming"))
        
        # Sync item_group with categories
        sync_item_group_with_categories(doc)


def sync_item_group_with_categories(doc):
    """
    Sync item_group field with category1 and category2.
    Uses format: {Cat1Code}-{Cat2Code} (e.g., E-STD, M-CUS)
    """
    if not doc.get("category1") or not doc.get("category2"):
        return
    
    # Extract codes from full names
    cat1_code, cat2_code = get_category_code(doc.category1, doc.category2)
    
    if cat1_code and cat2_code:
        # Item group name format: E-STD, M-CAT, etc.
        item_group_name = f"{cat1_code}-{cat2_code}"
        
        if frappe.db.exists("Item Group", item_group_name):
            doc.item_group = item_group_name
        else:
            # Fall back to main category
            if frappe.db.exists("Item Group", doc.category1):
                doc.item_group = doc.category1
