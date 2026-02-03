frappe.ui.form.on('Item', {
    setup: function(frm) {
        frm.save_action = null;
        frm.skip_save_dialog = false;
        frm.plm_save_in_progress = false;
        frm.plm_dialog_open = false;
        
        // Format attachment field to show only filename
        frm.set_query('link', 'custom_document_list', function() {
            return {
                filters: {
                    'docstatus': 1
                }
            };
        });
    },
    
    refresh: function(frm) {
        setup_auto_naming(frm);
        
        if (frm.is_new()) return;
        
        // Reset ALL flags on refresh to ensure clean state
        frm.skip_save_dialog = false;
        frm.plm_save_in_progress = false;
        frm.plm_dialog_open = false;
        
        check_user_permission(frm);
        add_version_control_buttons(frm);
        add_download_button(frm);
        add_version_history_button(frm);
        show_status_indicator(frm);
        
        // Override the save button to show our dialog
        override_save_button(frm);
        
        // Also override Ctrl+S keyboard shortcut
        override_keyboard_save(frm);
        
        // Safety: reset plm_save_in_progress after 30 seconds to prevent stuck state
        setTimeout(function() {
            if (frm.plm_save_in_progress) {
                console.warn('PLM: Resetting stuck plm_save_in_progress flag');
                frm.plm_save_in_progress = false;
            }
        }, 30000);
    },
    
    before_save: function(frm) {
        // Always allow new items to save normally
        if (frm.is_new()) return;
        
        // If we're in a PLM save action, allow save to proceed
        if (frm.plm_save_in_progress === true) {
            return;
        }
        
        // ALWAYS block the save for existing items without going through dialog
        frappe.validated = false;
        
        // Reset dialog flag if it was stuck
        if (!$('.modal.show').length) {
            frm.plm_dialog_open = false;
        }
        
        // Show error message to guide user
        frappe.show_alert({
            message: __('Please use the Save button to save with version control'),
            indicator: 'orange'
        }, 3);
        
        // Use setTimeout to avoid blocking the save process
        setTimeout(function() {
            show_save_action_dialog(frm);
        }, 100);
        
        return false;  // Extra safeguard to block save
    },
    
    use_auto_naming: function(frm) {
        toggle_item_code_field(frm);
        update_code_preview(frm);
        sync_item_group(frm);
    },
    
    category1: function(frm) {
        update_code_preview(frm);
        sync_item_group(frm);
    },
    
    category2: function(frm) {
        update_code_preview(frm);
        sync_item_group(frm);
    }
});

function override_keyboard_save(frm) {
    // Override Ctrl+S to show our dialog instead of direct save
    $(frm.wrapper).off('keydown.plm_save').on('keydown.plm_save', function(e) {
        if ((e.ctrlKey || e.metaKey) && e.key === 's') {
            if (!frm.is_new() && !frm.plm_save_in_progress) {
                e.preventDefault();
                e.stopPropagation();
                show_save_action_dialog(frm);
                return false;
            }
        }
    });
}

function override_save_button(frm) {
    // Remove existing primary action and add our custom one
    if (frm.is_new()) return;
    
    // Override the page primary action (Save button)
    frm.page.set_primary_action(__('Save'), function() {
        show_save_action_dialog(frm);
    });
}

function show_save_action_dialog(frm) {
    // Prevent multiple dialogs
    if (frm.plm_dialog_open) return;
    frm.plm_dialog_open = true;
    
    let current_status = frm.doc.plm_status || 'Draft';
    let current_version = frm.doc.current_version || 0;
    
    // Determine if version will increment
    // Version only increments when: Published -> any save, or Restore
    let will_increment = (current_status === 'Published');
    let next_version = will_increment ? current_version + 1 : current_version;
    
    // For first save (v0), publishing creates v1
    if (current_version === 0) {
        next_version = 1;
    }
    
    let version_note = '';
    if (will_increment) {
        version_note = `<p class="text-warning"><strong>${__('Note')}:</strong> ${__('Saving from Published status will create a new version (v{0})', [next_version])}</p>`;
    } else if (current_version === 0) {
        version_note = `<p class="text-info"><strong>${__('Note')}:</strong> ${__('First publish will create v1')}</p>`;
    }
    
    // Fetch current version's ECN to pre-fill the field
    frappe.call({
        method: 'plm_customizations.api.item_version.get_current_version_ecn',
        args: { item_code: frm.doc.name },
        async: false,
        callback: function(r) {
            let current_ecn = r.message || '';
            
            let d = new frappe.ui.Dialog({
                title: __('Save Options'),
                fields: [
                    {
                        fieldtype: 'HTML',
                        options: `
                            <div class="save-action-info" style="margin-bottom: 15px;">
                                <p><strong>${__('Current Status')}:</strong> 
                                    <span class="indicator ${get_status_color(current_status)}">${current_status}</span>
                                </p>
                                <p><strong>${__('Current Version')}:</strong> v${current_version}</p>
                                ${version_note}
                            </div>
                            <p>${__('How would you like to save these changes?')}</p>
                        `
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
                primary_action_label: get_publish_label(current_status, current_version),
                primary_action: function(values) {
                    if (!values.ecn) {
                        frappe.msgprint(__('ECN is required'));
                        return;
                    }
                    d.hide();
                    execute_save_action(frm, 'publish', values.notes, values.ecn);
                },
                secondary_action_label: __('Cancel'),
                secondary_action: function() {
                    d.hide();
                }
            });
            
            // Add custom buttons
            d.$wrapper.find('.modal-footer').prepend(`
                <button class="btn btn-warning btn-save-draft" style="margin-right: 8px;">
                    ${get_draft_label(current_status, current_version)}
                </button>
                <button class="btn btn-danger btn-block-item" style="margin-right: 8px;">
                    ${__('Block')}
                </button>
            `);
            
            d.$wrapper.find('.btn-save-draft').on('click', function() {
                let ecn = d.get_value('ecn');
                if (!ecn) {
                    frappe.msgprint(__('ECN is required'));
                    return;
                }
                let notes = d.get_value('notes');
                d.hide();
                execute_save_action(frm, 'draft', notes, ecn);
            });
            
            d.$wrapper.find('.btn-block-item').on('click', function() {
                let ecn = d.get_value('ecn');
                if (!ecn) {
                    frappe.msgprint(__('ECN is required'));
                    return;
                }
                let notes = d.get_value('notes');
                d.hide();
                execute_save_action(frm, 'block', notes, ecn);
            });
            
            // Handle dialog close
            d.onhide = function() {
                frm.plm_dialog_open = false;
            };
            
            d.show();
        }
    });
}

function get_publish_label(current_status, current_version) {
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

function get_draft_label(current_status, current_version) {
    if (current_status === 'Published') {
        // Published -> draft means new version
        return __('Save as Draft (v{0})', [current_version + 1]);
    } else {
        // Draft -> draft, same version
        return __('Save as Draft');
    }
}

function execute_save_action(frm, action, notes, ecn) {
    // Validate ECN is provided
    if (!ecn) {
        frappe.msgprint({
            title: __('Validation Error'),
            message: __('ECN is required to save changes'),
            indicator: 'red'
        });
        return;
    }
    
    // Set flag to allow save to proceed
    frm.plm_save_in_progress = true;
    
    // Save the document first
    frm.save().then(() => {
        let method;
        let success_msg;
        let indicator;
        
        if (action === 'publish') {
            method = 'plm_customizations.api.item_version.publish_item';
            success_msg = __('Published successfully');
            indicator = 'green';
        } else if (action === 'draft') {
            method = 'plm_customizations.api.item_version.save_as_draft';
            success_msg = __('Saved as draft');
            indicator = 'orange';
        } else if (action === 'block') {
            method = 'plm_customizations.api.item_version.block_item';
            success_msg = __('Item blocked');
            indicator = 'red';
        }
        
        frappe.call({
            method: method,
            args: {
                item_code: frm.doc.name,
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
            error: function(err) {
                frm.plm_save_in_progress = false;
                console.error('PLM save error:', err);
                frappe.msgprint({
                    title: __('Error'),
                    message: __('Failed to save. Please try again.'),
                    indicator: 'red'
                });
            }
        });
    }).catch((err) => {
        frm.plm_save_in_progress = false;
        console.error('PLM document save error:', err);
    });
}

function get_status_color(status) {
    if (status === 'Published') return 'green';
    if (status === 'Blocked') return 'red';
    return 'orange';
}

function sync_item_group(frm) {
    if (frm.doc.use_auto_naming && frm.doc.category1 && frm.doc.category2) {
        let cat1_code = frm.doc.category1.split(' - ')[0];
        let cat2_code = frm.doc.category2.split(' - ')[0];
        let item_group_name = `${cat1_code}-${cat2_code}`;
        
        frappe.db.exists("Item Group", item_group_name).then(exists => {
            if (exists) {
                frm.set_value('item_group', item_group_name);
            }
        });
    }
}

function setup_auto_naming(frm) {
    toggle_item_code_field(frm);
    
    if (frm.is_new() && frm.doc.use_auto_naming) {
        update_code_preview(frm);
    }
}

function toggle_item_code_field(frm) {
    if (frm.is_new()) {
        if (frm.doc.use_auto_naming) {
            frm.set_df_property('item_code', 'read_only', 1);
            frm.set_df_property('item_code', 'description', 
                __('Item code will be auto-generated based on selected categories'));
        } else {
            frm.set_df_property('item_code', 'read_only', 0);
            frm.set_df_property('item_code', 'description', 
                __('Enter your own item code or enable auto-generation'));
        }
    }
}

function update_code_preview(frm) {
    if (!frm.doc.use_auto_naming) {
        frm.set_value('generated_code_preview', '');
        return;
    }
    
    if (frm.doc.category1 && frm.doc.category2) {
        frappe.call({
            method: 'plm_customizations.api.item_naming.preview_item_code',
            args: {
                category1: frm.doc.category1,
                category2: frm.doc.category2
            },
            callback: function(r) {
                if (r.message) {
                    frm.set_value('generated_code_preview', r.message);
                    if (frm.is_new()) {
                        frm.set_value('item_code', r.message);
                    }
                }
            }
        });
    } else {
        frm.set_value('generated_code_preview', __('Select both categories to preview'));
    }
}

function check_user_permission(frm) {
    frm.has_publish_permission = false;
    frappe.call({
        method: 'plm_customizations.api.item_version.has_publish_permission',
        async: false,
        callback: function(r) {
            frm.has_publish_permission = r.message || false;
        }
    });
}

function add_version_control_buttons(frm) {
    if (!frm.has_publish_permission) return;
    
    let status = frm.doc.plm_status || 'Draft';
    
    if (status === 'Blocked') {
        frm.add_custom_button(__('Unblock'), function() {
            unblock_item(frm);
        }, __('Version Control'));
    }
}

function unblock_item(frm) {
    frappe.call({
        method: 'plm_customizations.api.item_version.unblock_item',
        args: {
            item_code: frm.doc.name
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

function add_version_history_button(frm) {
    frm.add_custom_button(__('View Version History'), function() {
        show_version_history(frm);
    }, __('Version Control'));
    
    // Add Compare Versions button
    frm.add_custom_button(__('Compare Versions'), function() {
        show_version_compare_dialog(frm);
    }, __('Version Control'));
}

function show_version_history(frm) {
    frappe.call({
        method: 'plm_customizations.api.item_version.get_version_history',
        args: {
            item_code: frm.doc.name
        },
        callback: function(r) {
            if (!r.message || r.message.length === 0) {
                frappe.msgprint(__('No version history found'));
                return;
            }
            
            let versions = r.message;
            let html = `
                <table class="table table-bordered">
                    <thead>
                        <tr>
                            <th>${__('Version')}</th>
                            <th>${__('ECN')}</th>
                            <th>${__('Status')}</th>
                            <th>${__('Date')}</th>
                            <th>${__('By')}</th>
                            <th>${__('Notes')}</th>
                            <th>${__('Actions')}</th>
                        </tr>
                    </thead>
                    <tbody>
            `;
            
            versions.forEach(v => {
                let status_color = v.status === 'Published' ? 'green' : 
                                   v.status === 'Blocked' ? 'red' : 'orange';
                let ecn_display = v.ecn_number ? 
                    `<a href="/app/ecn/${v.ecn}">${v.ecn_number}</a>` : '-';
                html += `
                    <tr>
                        <td><strong>v${v.version}</strong></td>
                        <td>${ecn_display}</td>
                        <td><span class="indicator ${status_color}">${v.status}</span></td>
                        <td>${frappe.datetime.str_to_user(v.published_date) || '-'}</td>
                        <td>${v.published_by || '-'}</td>
                        <td>${v.notes || '-'}</td>
                        <td>
                            <button class="btn btn-xs btn-default view-version-btn" data-version="${v.name}">
                                ${__('View')}
                            </button>
                            <button class="btn btn-xs btn-primary restore-version-btn" data-version="${v.name}" data-version-num="${v.version}">
                                ${__('Restore')}
                            </button>
                        </td>
                    </tr>
                `;
            });
            
            html += '</tbody></table>';
            
            let d = new frappe.ui.Dialog({
                title: __('Version History - {0}', [frm.doc.name]),
                size: 'large'
            });
            d.$body.html(html);
            
            d.$body.find('.view-version-btn').on('click', function() {
                let version_name = $(this).data('version');
                show_version_details(version_name);
            });
            
            d.$body.find('.restore-version-btn').on('click', function() {
                let version_name = $(this).data('version');
                let version_num = $(this).data('version-num');
                d.hide();
                restore_version(frm, version_name, version_num);
            });
            
            d.show();
        }
    });
}

function show_version_details(version_name) {
    frappe.call({
        method: 'plm_customizations.api.item_version.get_version_data',
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
            
            html += `<h5>${__('Basic Information')}</h5>`;
            html += '<table class="table table-bordered table-sm">';
            html += `<tr><td><strong>${__('Item Code')}</strong></td><td>${data.item_code || '-'}</td></tr>`;
            html += `<tr><td><strong>${__('Item Name')}</strong></td><td>${data.item_name || '-'}</td></tr>`;
            html += `<tr><td><strong>${__('Description')}</strong></td><td>${data.description || '-'}</td></tr>`;
            html += `<tr><td><strong>${__('Item Group')}</strong></td><td>${data.item_group || '-'}</td></tr>`;
            html += `<tr><td><strong>${__('Stock UOM')}</strong></td><td>${data.stock_uom || '-'}</td></tr>`;
            html += '</table>';
            
            if (data.current_version) {
                html += `<h5>${__('Version Info')}</h5>`;
                html += '<table class="table table-bordered table-sm">';
                html += `<tr><td><strong>${__('Version')}</strong></td><td>v${data.current_version}</td></tr>`;
                html += `<tr><td><strong>${__('PLM Status')}</strong></td><td>${data.plm_status || '-'}</td></tr>`;
                html += '</table>';
            }
            
            if (data.custom_document_list && data.custom_document_list.length > 0) {
                html += `<h5>${__('Document List')}</h5>`;
                html += '<table class="table table-bordered table-sm">';
                html += `<tr><th>${__('Link')}</th><th>${__('Type')}</th><th>${__('Revision')}</th></tr>`;
                data.custom_document_list.forEach(doc => {
                    html += `<tr><td>${doc.link || '-'}</td><td>${doc.type || '-'}</td><td>${doc.revision || '-'}</td></tr>`;
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

function restore_version(frm, version_name, version_num) {
    frappe.confirm(
        __('Restore version v{0}? This will create a new draft version with the restored data.', [version_num]),
        function() {
            frappe.call({
                method: 'plm_customizations.api.item_version.restore_version',
                args: {
                    item_code: frm.doc.name,
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

function add_download_button(frm) {
    frappe.call({
        method: 'plm_customizations.api.item_version.can_download_documents',
        args: {
            item_code: frm.doc.name
        },
        callback: function(r) {
            if (r.message && r.message.can_download) {
                frm.add_custom_button(__('Download All Documents'), function() {
                    download_all_documents(frm);
                });
            } else if (r.message) {
                frm.add_custom_button(__('Download Blocked'), function() {
                    frappe.msgprint({
                        title: __('Download Not Available'),
                        message: __(r.message.reason),
                        indicator: 'red'
                    });
                });
            }
        }
    });
}

function download_all_documents(frm) {
    // First get available versions
    frappe.call({
        method: 'plm_customizations.api.item_version.get_downloadable_versions',
        args: {
            item_code: frm.doc.name
        },
        callback: function(r) {
            if (!r.message || !r.message.versions || r.message.versions.length === 0) {
                frappe.msgprint(__('No versions available for download'));
                return;
            }
            
            let versions = r.message.versions;
            
            // Always show version selection dialog
            let version_options = versions.map(v => {
                return {
                    label: `${v.label} (${v.document_count} ${__('documents')})`,
                    value: v.is_current ? 'current' : String(v.version)
                };
            });
            
            let d = new frappe.ui.Dialog({
                title: __('Select Version to Download'),
                fields: [
                    {
                        fieldname: 'version',
                        label: __('Version'),
                        fieldtype: 'Select',
                        options: version_options.map(o => o.value).join('\n'),
                        default: 'current',
                        reqd: 1
                    },
                    {
                        fieldname: 'version_info',
                        fieldtype: 'HTML',
                        options: `<div class="version-info-container"></div>`
                    }
                ],
                primary_action_label: __('Download'),
                primary_action: function(values) {
                    let selected = versions.find(v => 
                        (values.version === 'current' && v.is_current) || 
                        String(v.version) === values.version
                    );
                    d.hide();
                    start_download(frm.doc.name, values.version, selected ? selected.document_count : 0);
                }
            });
            
            // Update version info display
            d.fields_dict.version.$input.on('change', function() {
                let selected_value = $(this).val();
                let selected = versions.find(v => 
                    (selected_value === 'current' && v.is_current) || 
                    String(v.version) === selected_value
                );
                
                if (selected) {
                    let info_html = `
                        <div class="mt-3 p-3 bg-light rounded">
                            <div><strong>${__('Status')}:</strong> ${selected.status}</div>
                            <div><strong>${__('Documents')}:</strong> ${selected.document_count}</div>
                            ${selected.published_date ? `<div><strong>${__('Date')}:</strong> ${selected.published_date}</div>` : ''}
                        </div>
                    `;
                    d.$wrapper.find('.version-info-container').html(info_html);
                }
            });
            
            // Trigger initial update
            d.fields_dict.version.$input.trigger('change');
            
            d.show();
        }
    });
}

function start_download(item_code, version, doc_count) {
    frappe.show_alert({
        message: __('Preparing {0} documents for download...', [doc_count]),
        indicator: 'blue'
    });
    
    let url = `/api/method/plm_customizations.api.document_download.download_item_documents?item_code=${encodeURIComponent(item_code)}`;
    if (version && version !== 'current') {
        url += `&version=${encodeURIComponent(version)}`;
    }
    
    window.open(url, '_blank');
}

function show_status_indicator(frm) {
    let status = frm.doc.plm_status || 'Draft';
    let version = frm.doc.current_version || 0;
    
    let indicator_class = get_status_color(status);
    
    if (version > 0) {
        frm.set_intro(
            `<span class="indicator ${indicator_class}">
                ${__('Version')}: v${version} | ${__('Status')}: ${status}
            </span>`,
            indicator_class
        );
    } else {
        frm.set_intro(
            `<span class="indicator orange">
                ${__('New Item - Not yet versioned')}
            </span>`,
            'orange'
        );
    }
}

function show_version_compare_dialog(frm) {
    frappe.call({
        method: 'plm_customizations.api.item_version.get_version_history',
        args: {
            item_code: frm.doc.name
        },
        callback: function(r) {
            if (!r.message || r.message.length < 2) {
                frappe.msgprint(__('Need at least 2 versions to compare.'));
                return;
            }
            
            let versions = r.message;
            let options = versions.map(function(v) { return 'v' + v.version + ' - ' + v.status; }).join('\n');
            
            let d = new frappe.ui.Dialog({
                title: __('Compare Versions'),
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
                    compare_versions(frm, v1, v2);
                }
            });
            
            d.show();
        }
    });
}

function compare_versions(frm, version1, version2) {
    frappe.call({
        method: 'plm_customizations.api.item_version.compare_versions',
        args: {
            item_code: frm.doc.name,
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
            
            if (diff.documents_added && diff.documents_added.length > 0) {
                html += '<h5 class="text-success">' + __('Documents Added') + '</h5><ul>';
                diff.documents_added.forEach(function(doc) {
                    html += '<li>' + (doc.link || doc.type || '-') + '</li>';
                });
                html += '</ul>';
            }
            
            if (diff.documents_removed && diff.documents_removed.length > 0) {
                html += '<h5 class="text-danger">' + __('Documents Removed') + '</h5><ul>';
                diff.documents_removed.forEach(function(doc) {
                    html += '<li>' + (doc.link || doc.type || '-') + '</li>';
                });
                html += '</ul>';
            }
            
            if ((!diff.fields || !diff.fields.length) && 
                (!diff.documents_added || !diff.documents_added.length) && 
                (!diff.documents_removed || !diff.documents_removed.length)) {
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

