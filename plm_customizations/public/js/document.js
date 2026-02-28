frappe.ui.form.on('Document', {
	refresh: function(frm) {
		if (frm.doc.attachment && !frm.doc.filename) {
			frm.set_value('filename', frm.doc.attachment.split('/').pop());
		}
	},
	attachment: function(frm) {
		if (frm.doc.attachment) {
			frm.set_value('filename', frm.doc.attachment.split('/').pop());
		}
	},
	after_save: function(frm) {
		if (!frm.doc.name || !frm.doc.item) return;

		// The server-side after_insert already linked the Document to the Item.
		// Here we just reload the open Item form (if any) so the list reflects the new row.
		let item_form = null;

		try {
			item_form = frappe.get_form('Item');
		} catch(e) {}

		if (!item_form || !item_form.doc) {
			Object.values(frappe.pages || {}).forEach(function(page) {
				if (page.frm && page.frm.doctype === 'Item' && page.frm.doc) {
					item_form = page.frm;
				}
			});
		}

		if (!item_form || !item_form.doc) return;
		if (frm.doc.item !== item_form.doc.name) return;

		// Reload the Item form so the newly linked Document appears in the list
		item_form.reload_doc();
	}
});
