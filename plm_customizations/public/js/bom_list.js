/**
 * BOM List View customizations for PLM
 * Shows PLM version control status and ECN, hides unnecessary columns
 */

frappe.listview_settings['BOM'] = frappe.listview_settings['BOM'] || {};

// Add PLM fields to fetch
frappe.listview_settings['BOM'].add_fields = ['plm_status', 'current_version', 'current_ecn', 'is_active', 'is_default', 'has_variants'];

// Format PLM status column
frappe.listview_settings['BOM'].formatters = {
    plm_status: function(value, field, doc) {
        if (!value) return '';
        var version = doc.current_version || 0;
        var color = 'orange';
        if (value === 'Published') {
            color = 'green';
        } else if (value === 'Blocked') {
            color = 'red';
        }
        return '<span class="indicator-pill ' + color + '">v' + version + ' ' + __(value) + '</span>';
    }
};

// Function to hide unwanted columns
function hide_bom_columns(listview) {
    if (!listview || !listview.$page) return;
    
    // Columns to hide
    var columns_to_hide = ['status', 'is_active', 'is_default', 'has_variants'];
    
    columns_to_hide.forEach(function(fieldname) {
        // Hide by data-fieldname
        listview.$page.find('[data-fieldname="' + fieldname + '"]').hide();
    });
    
    // Also hide by column header text
    var headers_to_hide = ['Status', 'Is Active', 'Is Default', 'Has Variants'];
    listview.$page.find('.list-row-head .list-row-col, .result .list-row-col').each(function() {
        var $col = $(this);
        var text = $col.text().trim();
        if (headers_to_hide.indexOf(text) !== -1) {
            var index = $col.index();
            $col.hide();
            // Hide corresponding cells in data rows
            listview.$page.find('.list-row-container .list-row, .result').each(function() {
                $(this).find('.list-row-col').eq(index).hide();
            });
        }
    });
}

// Hide columns and add bulk delete
frappe.listview_settings['BOM'].onload = function(listview) {
    // Hide columns on load with multiple delays
    setTimeout(function() { hide_bom_columns(listview); }, 200);
    setTimeout(function() { hide_bom_columns(listview); }, 500);
    setTimeout(function() { hide_bom_columns(listview); }, 1000);
    
    // Add bulk delete action
    listview.page.add_action_item(__('Delete Selected'), function() {
        var selected = listview.get_checked_items();
        if (!selected.length) {
            frappe.msgprint(__('Please select BOMs to delete'));
            return;
        }
        
        var names = selected.map(function(d) { return d.name; });
        
        frappe.confirm(
            __('Delete {0} selected BOM(s) and their version history? This cannot be undone.', [names.length]),
            function() {
                frappe.call({
                    method: 'plm_customizations.api.bom_version.bulk_delete_boms',
                    args: { bom_names: names },
                    callback: function(r) {
                        if (r.message) {
                            var msg = '';
                            if (r.message.deleted && r.message.deleted.length) {
                                msg += __('Deleted: {0}', [r.message.deleted.join(', ')]) + '<br>';
                            }
                            if (r.message.failed && r.message.failed.length) {
                                msg += '<br><strong>' + __('Failed:') + '</strong><br>';
                                r.message.failed.forEach(function(f) {
                                    msg += f.name + ': ' + f.error + '<br>';
                                });
                            }
                            frappe.msgprint({
                                title: __('Bulk Delete Results'),
                                message: msg,
                                indicator: r.message.failed && r.message.failed.length ? 'orange' : 'green'
                            });
                            listview.refresh();
                        }
                    }
                });
            }
        );
    });
};

// Also hide on refresh
frappe.listview_settings['BOM'].refresh = function(listview) {
    setTimeout(function() { hide_bom_columns(listview); }, 100);
    setTimeout(function() { hide_bom_columns(listview); }, 300);
};
