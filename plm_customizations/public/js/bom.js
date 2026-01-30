frappe.ui.form.on('BOM', {
    setup: function(frm) {
        frm.save_action = null;
        frm.skip_save_dialog = false;
        frm.plm_save_in_progress = false;
        frm.plm_dialog_open = false;
    },
    
    refresh: function(frm) {
        if (frm.is_new()) return;
        
        // Reset ALL flags on refresh to ensure clean state
        frm.skip_save_dialog = false;
        frm.plm_save_in_progress = false;
        frm.plm_dialog_open = false;
        
        // Hide ERPNext's version control buttons (Submit, Amend, New Version) - use PLM instead
        hide_erpnext_version_buttons(frm);
        
        // Check user permission for version control
        check_bom_user_permission(frm);
        
        // Add PLM version control buttons
        add_plm_version_buttons(frm);
        
        // Show PLM status indicator
        show_plm_status_indicator(frm);
        
        // Override the save button to show our dialog
        override_bom_save_button(frm);
        
        // Also override Ctrl+S keyboard shortcut
        override_keyboard_save(frm);
    },
    
    before_save: function(frm) {
        // Always allow new BOMs to save normally
        if (frm.is_new()) return;
        
        // If we're in a PLM save action, allow save to proceed
        if (frm.plm_save_in_progress) {
            return;
        }
        
        // Otherwise, cancel save and show dialog
        frappe.validated = false;
        
        // Reset dialog flag if it was stuck
        if (!$('.modal.show').length) {
            frm.plm_dialog_open = false;
        }
        
        // Use setTimeout to avoid blocking the save process
        setTimeout(function() {
            show_bom_save_action_dialog(frm);
        }, 100);
    }
});

function hide_erpnext_version_buttons(frm) {
    // Hide ERPNext's Submit, Amend, New Version buttons - PLM handles versioning
    setTimeout(function() {
        // Hide Submit button
        frm.page.btn_primary && frm.page.btn_primary.filter(function() {
            return $(this).text().trim() === __('Submit');
        }).hide();
        
        // Hide New Version button from menu
        frm.page.menu.find('a:contains("New Version")').parent().hide();
        frm.page.menu.find('a:contains("Amend")').parent().hide();
        
        // Remove from custom buttons if added
        frm.remove_custom_button(__('New Version'));
        frm.remove_custom_button(__('Submit'));
    }, 100);
    
    // If BOM is submitted (docstatus=1), offer to convert to PLM mode (unsubmit)
    if (frm.doc.docstatus === 1) {
        frm.add_custom_button(__('Convert to PLM Mode'), function() {
            frappe.confirm(
                __('This will unsubmit the BOM so it can be edited using PLM version control. The BOM will remain active and usable. Continue?'),
                function() {
                    frappe.call({
                        method: 'plm_customizations.api.bom_version.convert_bom_to_plm_mode',
                        args: { bom_name: frm.doc.name },
                        callback: function(r) {
                            if (r.message && r.message.success) {
                                frappe.show_alert({
                                    message: r.message.message,
                                    indicator: 'green'
                                });
                                frm.reload_doc();
                            }
                        }
                    });
                }
            );
        }, __('PLM Version'));
    }
}

function override_keyboard_save(frm) {
    // Override Ctrl+S to show our dialog instead of direct save
    $(frm.wrapper).off('keydown.plm_save').on('keydown.plm_save', function(e) {
        if ((e.ctrlKey || e.metaKey) && e.key === 's') {
            if (!frm.is_new() && !frm.plm_save_in_progress) {
                e.preventDefault();
                e.stopPropagation();
                show_bom_save_action_dialog(frm);
                return false;
            }
        }
    });
}

function override_bom_save_button(frm) {
    // Remove existing primary action and add our custom one
    if (frm.is_new()) return;
    
    // Override the page primary action (Save button)
    frm.page.set_primary_action(__('Save'), function() {
        show_bom_save_action_dialog(frm);
    });
}

function show_bom_save_action_dialog(frm) {
    // Prevent multiple dialogs
    if (frm.plm_dialog_open) return;
    frm.plm_dialog_open = true;
    
    let current_status = frm.doc.plm_status || 'Draft';
    let current_version = frm.doc.current_version || 0;
    
    // Determine if version will increment
    // Version increments when: Published -> Publish or Published -> Draft
    // Version does NOT increment for Block
    let will_increment_publish = (current_status === 'Published');
    let will_increment_draft = (current_status === 'Published');
    let next_version_publish = will_increment_publish ? current_version + 1 : current_version;
    let next_version_draft = will_increment_draft ? current_version + 1 : current_version;
    
    // For first save (v0), publishing creates v1
    if (current_version === 0) {
        next_version_publish = 1;
        next_version_draft = 1;
    }
    
    let version_note = '';
    if (will_increment_publish) {
        version_note = '<p class="text-warning"><strong>' + __('Note') + ':</strong> ' + 
            __('Publishing from Published status will create a new version (v{0})', [next_version_publish]) + '</p>';
    } else if (current_version === 0) {
        version_note = '<p class="text-info"><strong>' + __('Note') + ':</strong> ' + 
            __('First publish will create v1') + '</p>';
    }
    
    // Fetch current version's ECN to pre-fill the field
    frappe.call({
        method: 'plm_customizations.api.bom_version.get_current_bom_version_ecn',
        args: { bom_name: frm.doc.name },
        async: false,
        callback: function(r) {
            let current_ecn = r.message || '';
            
            let d = new frappe.ui.Dialog({
                title: __('Save Options'),
                fields: [
                    {
                        fieldtype: 'HTML',
                        options: '<div class="save-action-info" style="margin-bottom: 15px;">' +
                            '<p><strong>' + __('Current Status') + ':</strong> ' +
                            '<span class="indicator ' + get_bom_status_color(current_status) + '">' + current_status + '</span></p>' +
                            '<p><strong>' + __('Current Version') + ':</strong> v' + current_version + '</p>' +
                            version_note +
                            '</div>' +
                            '<p>' + __('How would you like to save these changes?') + '</p>'
                    },
                    {
                        label: __('ECN (Engineering Change Note)'),
                        fieldname: 'ecn',
                        fieldtype: 'Link',
                        options: 'ECN',
                        reqd: 1,
                        default: current_ecn,
                        description: __('Select the ECN for this version change')
                    },
                    {
                        label: __('Version Notes'),
                        fieldname: 'notes',
                        fieldtype: 'Small Text',
                        description: __('Describe the changes (optional)')
                    }
                ],
                primary_action_label: get_bom_publish_label(current_status, current_version),
                primary_action: function(values) {
                    if (!values.ecn) {
                        frappe.msgprint(__('ECN is required'));
                        return;
                    }
                    d.hide();
                    execute_bom_save_action(frm, 'publish', values.notes, values.ecn);
                },
                secondary_action_label: __('Cancel'),
                secondary_action: function() {
                    d.hide();
                }
            });
            
            // Handle dialog close
            d.onhide = function() {
                frm.plm_dialog_open = false;
            };
            
            // Add custom buttons
            d.$wrapper.find('.modal-footer').prepend(
                '<button class="btn btn-warning btn-save-draft" style="margin-right: 8px;">' +
                get_bom_draft_label(current_status, current_version) +
                '</button>' +
                '<button class="btn btn-danger btn-block-bom" style="margin-right: 8px;">' +
                __('Block (v{0})', [current_version || 1]) +
                '</button>'
            );
            
            d.$wrapper.find('.btn-save-draft').on('click', function() {
                let ecn = d.get_value('ecn');
                if (!ecn) {
                    frappe.msgprint(__('ECN is required'));
                    return;
                }
                let notes = d.get_value('notes');
                d.hide();
                execute_bom_save_action(frm, 'draft', notes, ecn);
            });
            
            d.$wrapper.find('.btn-block-bom').on('click', function() {
                let ecn = d.get_value('ecn');
                if (!ecn) {
                    frappe.msgprint(__('ECN is required'));
                    return;
                }
                let notes = d.get_value('notes');
                d.hide();
                execute_bom_save_action(frm, 'block', notes, ecn);
            });
            
            d.show();
        }
    });
}

function get_bom_publish_label(current_status, current_version) {
    if (current_version === 0) {
        return __('Publish (v1)');
    } else if (current_status === 'Published') {
        // Published -> publish again means new version
        return __('Publish (v{0})', [current_version + 1]);
    } else {
        // Draft -> publish, same version
        return __('Publish (v{0})', [current_version]);
    }
}

function get_bom_draft_label(current_status, current_version) {
    if (current_status === 'Published') {
        // Published -> draft means new version
        return __('Save as Draft (v{0})', [current_version + 1]);
    } else {
        // Draft -> draft, same version
        return __('Save as Draft');
    }
}

function execute_bom_save_action(frm, action, notes, ecn) {
    // Set flag to allow save to proceed
    frm.plm_save_in_progress = true;
    
    let method, success_msg, indicator;
    
    if (action === 'publish') {
        method = 'plm_customizations.api.bom_version.publish_bom';
        success_msg = __('Published successfully');
        indicator = 'green';
    } else if (action === 'draft') {
        method = 'plm_customizations.api.bom_version.save_bom_as_draft';
        success_msg = __('Saved as draft');
        indicator = 'orange';
    } else if (action === 'block') {
        method = 'plm_customizations.api.bom_version.block_bom';
        success_msg = __('BOM blocked');
        indicator = 'red';
    }
    
    // PLM: BOM always stays docstatus=0 (editable), save normally then call version action
    frm.save().then(function() {
        call_bom_version_action(frm, method, notes, ecn, success_msg, indicator);
    }).catch(function() {
        frm.plm_save_in_progress = false;
    });
}

function call_bom_version_action(frm, method, notes, ecn, success_msg, indicator) {
    frappe.call({
        method: method,
        args: {
            bom_name: frm.doc.name,
            notes: notes || '',
            ecn: ecn || ''
        },
        callback: function(r) {
            frm.plm_save_in_progress = false;
            if (r.message && r.message.success) {
                frappe.show_alert({
                    message: r.message.message || success_msg,
                    indicator: indicator
                });
                frm.reload_doc();
            } else if (r.message && r.message.error) {
                frappe.msgprint({
                    title: __('Error'),
                    message: r.message.error,
                    indicator: 'red'
                });
            }
        },
        error: function() {
            frm.plm_save_in_progress = false;
        }
    });
}

function check_bom_user_permission(frm) {
    frm.has_bom_publish_permission = false;
    frappe.call({
        method: 'plm_customizations.api.bom_version.has_bom_publish_permission',
        async: false,
        callback: function(r) {
            frm.has_bom_publish_permission = r.message || false;
        }
    });
}

function add_plm_version_buttons(frm) {
    let status = frm.doc.plm_status || 'Draft';
    
    // Add unblock button if blocked
    if (frm.has_bom_publish_permission && status === 'Blocked') {
        frm.add_custom_button(__('Unblock'), function() {
            unblock_bom(frm);
        }, __('PLM Version'));
    }
    
    // View History button - available to all users
    frm.add_custom_button(__('Version History'), function() {
        show_bom_version_history(frm);
    }, __('PLM Version'));
    
    // Compare Versions button
    frm.add_custom_button(__('Compare Versions'), function() {
        show_bom_version_compare_dialog(frm);
    }, __('PLM Version'));
    
    // Delete button
    if (frm.has_bom_publish_permission) {
        frm.add_custom_button(__('Delete BOM'), function() {
            frappe.confirm(
                __('Are you sure you want to delete this BOM and all its version history? This cannot be undone.'),
                function() {
                    frappe.call({
                        method: 'plm_customizations.api.bom_version.delete_bom',
                        args: { bom_name: frm.doc.name },
                        callback: function(r) {
                            if (r.message && r.message.success) {
                                frappe.show_alert({
                                    message: r.message.message,
                                    indicator: 'green'
                                });
                                frappe.set_route('List', 'BOM');
                            } else {
                                frappe.msgprint({
                                    title: __('Cannot Delete'),
                                    message: r.message ? r.message.error : __('Failed to delete'),
                                    indicator: 'red'
                                });
                            }
                        }
                    });
                }
            );
        }, __('PLM Version'));
    }
}

function unblock_bom(frm) {
    frappe.call({
        method: 'plm_customizations.api.bom_version.unblock_bom',
        args: {
            bom_name: frm.doc.name
        },
        callback: function(r) {
            if (r.message && r.message.success) {
                frappe.show_alert({
                    message: r.message.message,
                    indicator: 'green'
                });
                frm.reload_doc();
            }
        }
    });
}

function get_bom_status_color(status) {
    if (status === 'Published') return 'green';
    if (status === 'Blocked') return 'red';
    return 'orange';
}

function show_bom_version_history(frm) {
    frappe.call({
        method: 'plm_customizations.api.bom_version.get_bom_version_history',
        args: {
            bom_name: frm.doc.name
        },
        callback: function(r) {
            if (!r.message || r.message.length === 0) {
                frappe.msgprint(__('No version history found. Save the BOM to create a version.'));
                return;
            }
            
            let versions = r.message;
            let html = '<table class="table table-bordered">' +
                '<thead><tr>' +
                '<th>' + __('Version') + '</th>' +
                '<th>' + __('ECN') + '</th>' +
                '<th>' + __('Status') + '</th>' +
                '<th>' + __('Date') + '</th>' +
                '<th>' + __('By') + '</th>' +
                '<th>' + __('Notes') + '</th>' +
                '<th>' + __('Actions') + '</th>' +
                '</tr></thead><tbody>';
            
            versions.forEach(function(v) {
                let status_color = v.status === 'Published' ? 'green' : 
                                   v.status === 'Blocked' ? 'red' : 'orange';
                let ecn_display = v.ecn_number ? 
                    '<a href="/app/ecn/' + v.ecn + '">' + v.ecn_number + '</a>' : '-';
                html += '<tr>' +
                    '<td><strong>v' + v.version + '</strong></td>' +
                    '<td>' + ecn_display + '</td>' +
                    '<td><span class="indicator ' + status_color + '">' + v.status + '</span></td>' +
                    '<td>' + (frappe.datetime.str_to_user(v.published_date) || '-') + '</td>' +
                    '<td>' + (v.published_by || '-') + '</td>' +
                    '<td>' + (v.notes || '-') + '</td>' +
                    '<td>' +
                    '<button class="btn btn-xs btn-default view-bom-version-btn" data-version="' + v.name + '">' + __('View') + '</button> ' +
                    '<button class="btn btn-xs btn-primary restore-bom-version-btn" data-version="' + v.name + '" data-version-num="' + v.version + '">' + __('Restore') + '</button>' +
                    '</td></tr>';
            });
            
            html += '</tbody></table>';
            
            let d = new frappe.ui.Dialog({
                title: __('PLM Version History - {0}', [frm.doc.name]),
                size: 'large'
            });
            d.$body.html(html);
            
            d.$body.find('.view-bom-version-btn').on('click', function() {
                let version_name = $(this).data('version');
                show_bom_version_details(version_name);
            });
            
            d.$body.find('.restore-bom-version-btn').on('click', function() {
                let version_name = $(this).data('version');
                let version_num = $(this).data('version-num');
                d.hide();
                restore_bom_version(frm, version_name, version_num);
            });
            
            d.show();
        }
    });
}

function show_bom_version_details(version_name) {
    frappe.call({
        method: 'plm_customizations.api.bom_version.get_bom_version_data',
        args: {
            version_name: version_name
        },
        callback: function(r) {
            if (!r.message) {
                frappe.msgprint(__('Version data not found'));
                return;
            }
            
            let data = r.message;
            let html = '<div class="version-details" style="max-height: 500px; overflow-y: auto;">';
            
            html += '<h5>' + __('Basic Information') + '</h5>';
            html += '<table class="table table-bordered table-sm">';
            html += '<tr><td><strong>' + __('BOM') + '</strong></td><td>' + (data.name || '-') + '</td></tr>';
            html += '<tr><td><strong>' + __('Item') + '</strong></td><td>' + (data.item || '-') + '</td></tr>';
            html += '<tr><td><strong>' + __('Quantity') + '</strong></td><td>' + (data.quantity || '-') + '</td></tr>';
            html += '</table>';
            
            if (data.items && data.items.length > 0) {
                html += '<h5>' + __('BOM Items') + '</h5>';
                html += '<table class="table table-bordered table-sm">';
                html += '<tr><th>' + __('Item Code') + '</th><th>' + __('Item Name') + '</th><th>' + __('Qty') + '</th><th>' + __('UOM') + '</th></tr>';
                data.items.forEach(function(item) {
                    html += '<tr><td>' + (item.item_code || '-') + '</td><td>' + (item.item_name || '-') + '</td><td>' + (item.qty || '-') + '</td><td>' + (item.uom || '-') + '</td></tr>';
                });
                html += '</table>';
            }
            
            html += '</div>';
            
            let d = new frappe.ui.Dialog({
                title: __('Version Details - {0}', [version_name]),
                size: 'large'
            });
            d.$body.html(html);
            d.show();
        }
    });
}

function restore_bom_version(frm, version_name, version_num) {
    frappe.confirm(
        __('Restore version v{0}? This will create a new draft version with the restored data.', [version_num]),
        function() {
            frappe.call({
                method: 'plm_customizations.api.bom_version.restore_bom_version',
                args: {
                    bom_name: frm.doc.name,
                    version_name: version_name
                },
                callback: function(r) {
                    if (r.message && r.message.success) {
                        frappe.show_alert({
                            message: r.message.message,
                            indicator: 'green'
                        });
                        frm.reload_doc();
                    } else if (r.message && r.message.error) {
                        frappe.msgprint({
                            title: __('Error'),
                            message: r.message.error,
                            indicator: 'red'
                        });
                    }
                }
            });
        }
    );
}

function show_bom_version_compare_dialog(frm) {
    frappe.call({
        method: 'plm_customizations.api.bom_version.get_bom_version_history',
        args: {
            bom_name: frm.doc.name
        },
        callback: function(r) {
            if (!r.message || r.message.length < 2) {
                frappe.msgprint(__('Need at least 2 versions to compare.'));
                return;
            }
            
            let versions = r.message;
            let options = versions.map(function(v) { return 'v' + v.version + ' - ' + v.status; }).join('\n');
            
            let d = new frappe.ui.Dialog({
                title: __('Compare PLM Versions'),
                fields: [
                    {
                        fieldname: 'version1',
                        label: __('Version 1'),
                        fieldtype: 'Select',
                        options: options,
                        reqd: 1
                    },
                    {
                        fieldname: 'version2',
                        label: __('Version 2'),
                        fieldtype: 'Select',
                        options: options,
                        reqd: 1
                    }
                ],
                primary_action_label: __('Compare'),
                primary_action: function(values) {
                    let v1 = parseInt(values.version1.split(' ')[0].replace('v', ''));
                    let v2 = parseInt(values.version2.split(' ')[0].replace('v', ''));
                    d.hide();
                    compare_bom_versions(frm, v1, v2);
                }
            });
            
            d.show();
        }
    });
}

function compare_bom_versions(frm, version1, version2) {
    frappe.call({
        method: 'plm_customizations.api.bom_version.compare_bom_versions',
        args: {
            bom_name: frm.doc.name,
            version1: version1,
            version2: version2
        },
        callback: function(r) {
            if (!r.message || !r.message.success) {
                frappe.msgprint(r.message ? r.message.error : __('Comparison failed'));
                return;
            }
            
            let diff = r.message.differences;
            let html = '<div style="max-height: 500px; overflow-y: auto;">';
            
            if (diff.fields && diff.fields.length > 0) {
                html += '<h5>' + __('Field Changes') + '</h5>';
                html += '<table class="table table-bordered table-sm">';
                html += '<tr><th>' + __('Field') + '</th><th>v' + version1 + '</th><th>v' + version2 + '</th></tr>';
                diff.fields.forEach(function(f) {
                    html += '<tr><td>' + f.field + '</td><td>' + (f.version1 || '-') + '</td><td>' + (f.version2 || '-') + '</td></tr>';
                });
                html += '</table>';
            }
            
            if (diff.items_added && diff.items_added.length > 0) {
                html += '<h5 class="text-success">' + __('Items Added') + '</h5><ul>';
                diff.items_added.forEach(function(item) {
                    html += '<li>' + item.item_code + ' (Qty: ' + item.qty + ')</li>';
                });
                html += '</ul>';
            }
            
            if (diff.items_removed && diff.items_removed.length > 0) {
                html += '<h5 class="text-danger">' + __('Items Removed') + '</h5><ul>';
                diff.items_removed.forEach(function(item) {
                    html += '<li>' + item.item_code + ' (Qty: ' + item.qty + ')</li>';
                });
                html += '</ul>';
            }
            
            if ((!diff.fields || !diff.fields.length) && 
                (!diff.items_added || !diff.items_added.length) && 
                (!diff.items_removed || !diff.items_removed.length)) {
                html += '<p class="text-muted">' + __('No differences found') + '</p>';
            }
            
            html += '</div>';
            
            let dialog = new frappe.ui.Dialog({
                title: __('Comparison: v{0} vs v{1}', [version1, version2]),
                size: 'large'
            });
            dialog.$body.html(html);
            dialog.show();
        }
    });
}

function show_plm_status_indicator(frm) {
    let status = frm.doc.plm_status;
    let version = frm.doc.current_version;
    
    if (!version && !status) return;
    
    status = status || 'Draft';
    version = version || 0;
    
    if (version > 0) {
        frm.dashboard.add_indicator(
            __('PLM: v{0} ({1})', [version, status]),
            get_bom_status_color(status)
        );
    }
}
