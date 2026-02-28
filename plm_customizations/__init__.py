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


def _patch_csv_utf8_bom():
    """Add UTF-8 BOM to CSV exports so Excel correctly recognizes Chinese characters."""
    import codecs
    import frappe.desk.utils as desk_utils
    import frappe.utils.response as response_mod

    if getattr(desk_utils, "_plm_csv_bom_patched", False):
        return

    _original_get_csv_bytes = desk_utils.get_csv_bytes

    def get_csv_bytes_with_bom(data, csv_params):
        return codecs.BOM_UTF8 + _original_get_csv_bytes(data, csv_params)

    desk_utils.get_csv_bytes = get_csv_bytes_with_bom

    _original_as_csv = response_mod.as_csv

    def as_csv_with_bom():
        resp = _original_as_csv()
        if resp.data and not resp.data.startswith(codecs.BOM_UTF8):
            if isinstance(resp.data, str):
                resp.data = codecs.BOM_UTF8 + resp.data.encode("utf-8")
            else:
                resp.data = codecs.BOM_UTF8 + resp.data
        return resp

    response_mod.as_csv = as_csv_with_bom
    desk_utils._plm_csv_bom_patched = True


_patch_csv_utf8_bom()
