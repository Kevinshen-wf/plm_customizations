__version__ = "0.0.1"

# Patch Frappe FormMeta so custom doctypes still load doctype_js from hooks.
# (Frappe's add_code() returns early for custom, so doctype_js was never loaded.)
def _patch_form_meta_for_custom_doctype_js():
    import frappe.desk.form.meta as form_meta

    if getattr(form_meta.FormMeta, "_plm_custom_doctype_js_patched", False):
        return

    original_add_code = form_meta.FormMeta.add_code

    def add_code_with_custom_doctype_js(self):
        if self.custom:
            self.add_code_via_hook("doctype_js", "__js")
            self.add_code_via_hook("doctype_list_js", "__list_js")
            self.add_code_via_hook("doctype_tree_js", "__tree_js")
            self.add_code_via_hook("doctype_calendar_js", "__calendar_js")
            return
        return original_add_code(self)

    form_meta.FormMeta.add_code = add_code_with_custom_doctype_js
    form_meta.FormMeta._plm_custom_doctype_js_patched = True


_patch_form_meta_for_custom_doctype_js()
