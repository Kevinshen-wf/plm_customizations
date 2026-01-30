// Copyright (c) 2024, PLM Customizations and contributors
// For license information, please see license.txt

frappe.ui.form.on('ECN', {
    refresh: function(frm) {
        if (!frm.is_new()) {
            load_linked_versions(frm);
        }
    }
});

function load_linked_versions(frm) {
    frappe.call({
        method: 'plm_customizations.plm_customizations.doctype.ecn.ecn.get_linked_versions',
        args: {
            ecn_name: frm.doc.name
        },
        callback: function(r) {
            if (r.message) {
                render_item_versions(frm, r.message.item_versions);
                render_bom_versions(frm, r.message.bom_versions);
            }
        }
    });
}

function render_item_versions(frm, versions) {
    let html = '';
    
    if (versions && versions.length > 0) {
        html = `
            <table class="table table-bordered table-sm">
                <thead>
                    <tr>
                        <th>${__('Item Code')}</th>
                        <th>${__('Version')}</th>
                        <th>${__('Status')}</th>
                        <th>${__('Date')}</th>
                    </tr>
                </thead>
                <tbody>
        `;
        
        versions.forEach(v => {
            let status_color = v.status === 'Published' ? 'green' : 
                               v.status === 'Blocked' ? 'red' : 'orange';
            html += `
                <tr>
                    <td><a href="/app/item/${v.item_code}">${v.item_code}</a></td>
                    <td><strong>v${v.version}</strong></td>
                    <td><span class="indicator ${status_color}">${v.status}</span></td>
                    <td>${frappe.datetime.str_to_user(v.published_date) || '-'}</td>
                </tr>
            `;
        });
        
        html += '</tbody></table>';
    } else {
        html = `<p class="text-muted">${__('No Item Versions linked to this ECN')}</p>`;
    }
    
    frm.fields_dict.linked_item_versions_html.$wrapper.html(html);
}

function render_bom_versions(frm, versions) {
    let html = '';
    
    if (versions && versions.length > 0) {
        html = `
            <table class="table table-bordered table-sm">
                <thead>
                    <tr>
                        <th>${__('BOM')}</th>
                        <th>${__('Version')}</th>
                        <th>${__('Status')}</th>
                        <th>${__('Date')}</th>
                    </tr>
                </thead>
                <tbody>
        `;
        
        versions.forEach(v => {
            let status_color = v.status === 'Published' ? 'green' : 
                               v.status === 'Blocked' ? 'red' : 'orange';
            html += `
                <tr>
                    <td><a href="/app/bom/${v.bom}">${v.bom}</a></td>
                    <td><strong>v${v.version}</strong></td>
                    <td><span class="indicator ${status_color}">${v.status}</span></td>
                    <td>${frappe.datetime.str_to_user(v.published_date) || '-'}</td>
                </tr>
            `;
        });
        
        html += '</tbody></table>';
    } else {
        html = `<p class="text-muted">${__('No BOM Versions linked to this ECN')}</p>`;
    }
    
    frm.fields_dict.linked_bom_versions_html.$wrapper.html(html);
}
