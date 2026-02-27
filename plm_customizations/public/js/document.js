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
		// After saving a new Document, if opened via quick entry from Item's child table,
		// automatically add it to the custom_document_list child table
		if (frm.doc.__is_local || !frm.doc.name) return;

		// Check if there is a parent Item form open in the background
		let item_form = frappe.get_form('Item');
		if (!item_form || !item_form.doc) return;

		// Only auto-add if this Document's item matches the current Item
		if (frm.doc.item && frm.doc.item !== item_form.doc.name) return;

		// Check if this Document is already in the list
		let existing = (item_form.doc.custom_document_list || []).find(
			row => row.link === frm.doc.name
		);
		if (existing) return;

		// Add a new row to the child table
		let row = frappe.model.add_child(item_form.doc, 'Item Drawing Link', 'custom_document_list');
		frappe.model.set_value(row.doctype, row.name, 'link', frm.doc.name);
		item_form.refresh_field('custom_document_list');

		frappe.show_alert({
			message: __('Document {0} added to Document List', [frm.doc.name]),
			indicator: 'green'
		}, 4);
	}
});
