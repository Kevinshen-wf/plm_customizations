/**
 * Item List View customizations for PLM
 * Shows PLM version control status and ECN
 */

frappe.listview_settings['Item'] = frappe.listview_settings['Item'] || {};

// Add custom columns and formatting
frappe.listview_settings['Item'].add_fields = ['current_version', 'plm_status', 'current_ecn'];

frappe.listview_settings['Item'].get_indicator = function(doc) {
    // Show PLM status as indicator
    if (doc.plm_status === 'Published') {
        return [__('v{0} Published', [doc.current_version || 0]), 'green', 'plm_status,=,Published'];
    } else if (doc.plm_status === 'Blocked') {
        return [__('v{0} Blocked', [doc.current_version || 0]), 'red', 'plm_status,=,Blocked'];
    } else if (doc.plm_status === 'Draft') {
        return [__('v{0} Draft', [doc.current_version || 0]), 'orange', 'plm_status,=,Draft'];
    }
    // Fallback to default disabled status
    if (doc.disabled) {
        return [__('Disabled'), 'grey', 'disabled,=,1'];
    }
    return [__('Enabled'), 'blue', 'disabled,=,0'];
};
