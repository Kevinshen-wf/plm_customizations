/**
 * Document: use original Attach button.
 * Type field has no default value - user must select.
 */

frappe.ui.form.on('Document', {
	refresh: function(frm) {
		// Auto-populate filename from attachment
		if (frm.doc.attachment && !frm.doc.filename) {
			frm.set_value('filename', frm.doc.attachment.split('/').pop());
		}
	},
	attachment: function(frm) {
		// When attachment changes, update filename
		if (frm.doc.attachment) {
			frm.set_value('filename', frm.doc.attachment.split('/').pop());
		}
	}
});
