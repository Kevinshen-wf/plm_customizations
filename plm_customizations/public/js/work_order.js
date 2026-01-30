frappe.ui.form.on('Work Order', {
    refresh: function(frm) {
        if (frm.is_new()) return;
        
        // Show BOM version info
        show_bom_version_indicator(frm);
        
        // Check BOM status before operations
        check_bom_status_before_operation(frm);
        
        // Add button to view BOM snapshot
        if (frm.doc.bom_version && frm.doc.bom_snapshot_data) {
            frm.add_custom_button(__('View BOM Snapshot'), function() {
                show_bom_snapshot_dialog(frm);
            }, __('BOM Version'));
        }
    },
    
    bom_no: function(frm) {
        // When BOM is selected, validate and show info
        if (frm.doc.bom_no && frm.is_new()) {
            validate_bom_for_work_order(frm);
        }
    }
});

function show_bom_version_indicator(frm) {
    if (!frm.doc.bom_no) return;
    
    let bom_version = frm.doc.bom_version;
    
    if (bom_version) {
        // Check current BOM status
        frappe.call({
            method: 'plm_customizations.api.work_order_version.check_bom_status_for_operation',
            args: {
                work_order_name: frm.doc.name
            },
            callback: function(r) {
                if (r.message) {
                    let data = r.message;
                    
                    if (data.bom_blocked) {
                        // BOM is blocked - show warning
                        frm.dashboard.add_indicator(
                            __('BOM v{0} - BLOCKED', [bom_version]),
                            'red'
                        );
                        frm.set_intro(
                            '<span class="indicator red">' +
                            __('Warning: The BOM for this Work Order has been blocked. Manufacturing operations are suspended.') +
                            '</span>',
                            'red'
                        );
                    } else {
                        // Show version info
                        let indicator_text = __('Using BOM v{0}', [bom_version]);
                        
                        // Check if BOM has been updated since Work Order creation
                        if (data.current_bom_version && data.current_bom_version > bom_version) {
                            indicator_text = __('Using BOM v{0} (Latest: v{1})', [bom_version, data.current_bom_version]);
                            frm.dashboard.add_indicator(indicator_text, 'orange');
                        } else {
                            frm.dashboard.add_indicator(indicator_text, 'green');
                        }
                    }
                }
            }
        });
    }
}

function check_bom_status_before_operation(frm) {
    // Override buttons that trigger manufacturing operations
    if (frm.doc.docstatus === 1 && frm.doc.bom_no) {
        // Check BOM status
        frappe.call({
            method: 'plm_customizations.api.work_order_version.check_bom_status_for_operation',
            args: {
                work_order_name: frm.doc.name
            },
            async: false,
            callback: function(r) {
                if (r.message && r.message.bom_blocked) {
                    // Disable manufacturing buttons
                    frm.disable_save();
                    
                    // Remove standard action buttons
                    frm.page.clear_primary_action();
                    
                    // Add info message
                    frm.set_intro(
                        '<span class="indicator red">' +
                        __('Manufacturing suspended: BOM is blocked. Contact PLM administrator.') +
                        '</span>',
                        'red'
                    );
                }
            }
        });
    }
}

function validate_bom_for_work_order(frm) {
    if (!frm.doc.bom_no) return;
    
    // Get BOM PLM status
    frappe.db.get_value('BOM', frm.doc.bom_no, ['plm_status', 'current_version', 'docstatus', 'is_active'], function(r) {
        if (r) {
            let status = r.plm_status || 'Draft';
            let version = r.current_version || 0;
            
            if (r.docstatus !== 1) {
                frappe.msgprint({
                    title: __('BOM Not Submitted'),
                    message: __('BOM must be submitted (Published) before creating a Work Order.'),
                    indicator: 'red'
                });
                frm.set_value('bom_no', '');
                return;
            }
            
            if (status === 'Blocked') {
                frappe.msgprint({
                    title: __('BOM Blocked'),
                    message: __('Cannot use blocked BOM for Work Order. Please contact PLM administrator.'),
                    indicator: 'red'
                });
                frm.set_value('bom_no', '');
                return;
            }
            
            if (status === 'Draft' || version === 0) {
                frappe.msgprint({
                    title: __('BOM Not Published'),
                    message: __('BOM must be Published before creating a Work Order. Current status: {0}', [status]),
                    indicator: 'orange'
                });
                frm.set_value('bom_no', '');
                return;
            }
            
            // Show version info
            frappe.show_alert({
                message: __('BOM v{0} ({1}) will be used for this Work Order', [version, status]),
                indicator: 'green'
            });
        }
    });
}

function show_bom_snapshot_dialog(frm) {
    if (!frm.doc.bom_snapshot_data) {
        frappe.msgprint(__('No BOM snapshot data available'));
        return;
    }
    
    try {
        let snapshot = JSON.parse(frm.doc.bom_snapshot_data);
        
        let html = '<div style="max-height: 500px; overflow-y: auto;">';
        
        // Basic info
        html += '<h5>' + __('BOM Information') + '</h5>';
        html += '<table class="table table-bordered table-sm">';
        html += '<tr><td><strong>' + __('BOM') + '</strong></td><td>' + (snapshot.name || '-') + '</td></tr>';
        html += '<tr><td><strong>' + __('Item') + '</strong></td><td>' + (snapshot.item || '-') + '</td></tr>';
        html += '<tr><td><strong>' + __('Quantity') + '</strong></td><td>' + (snapshot.quantity || '-') + '</td></tr>';
        html += '<tr><td><strong>' + __('Version at Creation') + '</strong></td><td>v' + frm.doc.bom_version + '</td></tr>';
        html += '</table>';
        
        // Items
        if (snapshot.items && snapshot.items.length > 0) {
            html += '<h5>' + __('BOM Items (Snapshot)') + '</h5>';
            html += '<table class="table table-bordered table-sm">';
            html += '<tr><th>' + __('Item Code') + '</th><th>' + __('Item Name') + '</th><th>' + __('Qty') + '</th><th>' + __('UOM') + '</th></tr>';
            snapshot.items.forEach(function(item) {
                html += '<tr>';
                html += '<td>' + (item.item_code || '-') + '</td>';
                html += '<td>' + (item.item_name || '-') + '</td>';
                html += '<td>' + (item.qty || '-') + '</td>';
                html += '<td>' + (item.uom || '-') + '</td>';
                html += '</tr>';
            });
            html += '</table>';
        }
        
        // Operations
        if (snapshot.operations && snapshot.operations.length > 0) {
            html += '<h5>' + __('Operations (Snapshot)') + '</h5>';
            html += '<table class="table table-bordered table-sm">';
            html += '<tr><th>' + __('Operation') + '</th><th>' + __('Workstation') + '</th><th>' + __('Time (mins)') + '</th></tr>';
            snapshot.operations.forEach(function(op) {
                html += '<tr>';
                html += '<td>' + (op.operation || '-') + '</td>';
                html += '<td>' + (op.workstation || '-') + '</td>';
                html += '<td>' + (op.time_in_mins || '-') + '</td>';
                html += '</tr>';
            });
            html += '</table>';
        }
        
        html += '</div>';
        
        let d = new frappe.ui.Dialog({
            title: __('BOM Snapshot - v{0}', [frm.doc.bom_version]),
            size: 'large'
        });
        d.$body.html(html);
        d.show();
        
    } catch (e) {
        frappe.msgprint(__('Error parsing BOM snapshot data'));
    }
}
