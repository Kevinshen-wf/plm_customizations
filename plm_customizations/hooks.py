app_name = "plm_customizations"
app_title = "PLM Customizations"
app_publisher = "Your Company"
app_description = "PLM Customizations for ERPNext"
app_email = "your@email.com"
app_license = "MIT"

# Installation
# ------------
after_install = "plm_customizations.setup.after_install"
after_migrate = "plm_customizations.setup.after_install"

# Document Events
# ----------------
# Hook on document methods and events

doc_events = {
    "Document": {
        "after_insert": "plm_customizations.api.document_events.after_insert_document",
        "before_cancel": "plm_customizations.api.document_events.before_cancel_document",
        "on_cancel": "plm_customizations.api.document_events.on_cancel_document",
        "validate": "plm_customizations.api.document_events.validate_document"
    },
    "Item": {
        "before_insert": "plm_customizations.api.item_naming.before_insert_item",
        "validate": "plm_customizations.api.item_naming.validate_item"
    },
    "Work Order": {
        "validate": "plm_customizations.api.work_order_version.on_work_order_validate",
        "before_submit": "plm_customizations.api.work_order_version.on_work_order_before_submit"
    },
    "Job Card": {
        "validate": "plm_customizations.api.work_order_version.on_job_card_validate"
    },
    "Stock Entry": {
        "validate": "plm_customizations.api.work_order_version.on_stock_entry_validate"
    }
}

# Fixtures
# --------
fixtures = [
    {
        "dt": "Custom Field",
        "filters": [["dt", "=", "Item"]]
    },
    {
        "dt": "Role",
        "filters": [["role_name", "=", "Mechanical Engineer"]]
    },
    {
        "dt": "Custom DocPerm",
        "filters": [["role", "=", "Mechanical Engineer"]]
    },
    {
        "dt": "Document Naming Rule"
    }
]

# Includes in <head>
# ------------------

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in doctype views (Document loads via patch in __init__.py for custom doctype)
doctype_js = {
    "Document": "public/js/document.js",
    "Item": "public/js/item.js",
    "BOM": "public/js/bom.js",
    "Work Order": "public/js/work_order.js"
}

doctype_list_js = {
    "Item": "public/js/item_list.js",
    "BOM": "public/js/bom_list.js"
}

# Whitelisted Methods
# -------------------
# Methods that can be called from the client side

# override_whitelisted_methods = {
# }

# Jinja Environment
# -----------------
# jinja = {
#     "methods": [],
#     "filters": []
# }
