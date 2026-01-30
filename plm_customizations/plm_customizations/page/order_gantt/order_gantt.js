frappe.pages['order-gantt'].on_page_load = function(wrapper) {
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __('Order Gantt Chart'),
        single_column: true
    });
    
    // Store page reference
    wrapper.order_gantt = new OrderGantt(page);
};

frappe.pages['order-gantt'].on_page_show = function(wrapper) {
    if (wrapper.order_gantt) {
        wrapper.order_gantt.refresh();
    }
};

class OrderGantt {
    constructor(page) {
        this.page = page;
        this.gantt = null;
        this.tasks = [];
        this.filters = {
            project: null,
            from_date: null,
            to_date: null,
            order_types: ['purchase', 'work', 'sales']
        };
        
        this.setup_page();
        this.setup_filters();
        this.render();
    }
    
    setup_page() {
        // Add refresh button
        this.page.set_primary_action(__('Refresh'), () => this.refresh(), 'refresh');
        
        // Create main container
        this.page.main.html(`
            <div class="order-gantt-container">
                <div class="gantt-filters mb-4"></div>
                <div class="gantt-legend mb-3">
                    <span class="legend-item">
                        <span class="legend-color" style="background: var(--green-500);"></span> ${__('Completed')}
                    </span>
                    <span class="legend-item">
                        <span class="legend-color" style="background: var(--blue-500);"></span> ${__('Normal')}
                    </span>
                    <span class="legend-item">
                        <span class="legend-color" style="background: var(--orange-500);"></span> ${__('At Risk')}
                    </span>
                    <span class="legend-item">
                        <span class="legend-color" style="background: var(--red-500);"></span> ${__('Delayed')}
                    </span>
                </div>
                <div class="gantt-chart-wrapper" style="overflow-x: auto;">
                    <svg id="gantt-chart"></svg>
                </div>
                <div class="gantt-no-data text-center text-muted p-5" style="display: none;">
                    ${__('No orders found. Try adjusting the filters.')}
                </div>
            </div>
        `);
    }
    
    setup_filters() {
        let me = this;
        let $filters = this.page.main.find('.gantt-filters');
        
        $filters.html(`
            <div class="row">
                <div class="col-md-3">
                    <div class="form-group">
                        <label>${__('Project')}</label>
                        <select class="form-control filter-project">
                            <option value="">${__('All Projects')}</option>
                        </select>
                    </div>
                </div>
                <div class="col-md-2">
                    <div class="form-group">
                        <label>${__('From Date')}</label>
                        <input type="date" class="form-control filter-from-date">
                    </div>
                </div>
                <div class="col-md-2">
                    <div class="form-group">
                        <label>${__('To Date')}</label>
                        <input type="date" class="form-control filter-to-date">
                    </div>
                </div>
                <div class="col-md-5">
                    <div class="form-group">
                        <label>${__('Order Types')}</label>
                        <div class="order-type-checkboxes">
                            <label class="mr-3">
                                <input type="checkbox" class="filter-type" value="purchase" checked> ${__('Purchase Orders')}
                            </label>
                            <label class="mr-3">
                                <input type="checkbox" class="filter-type" value="work" checked> ${__('Work Orders')}
                            </label>
                            <label>
                                <input type="checkbox" class="filter-type" value="sales" checked> ${__('Sales Orders')}
                            </label>
                        </div>
                    </div>
                </div>
            </div>
        `);
        
        // Load projects
        frappe.call({
            method: 'plm_customizations.api.gantt_data.get_projects',
            callback: (r) => {
                if (r.message) {
                    let $select = $filters.find('.filter-project');
                    r.message.forEach(p => {
                        $select.append(`<option value="${p.name}">${p.project_name || p.name}</option>`);
                    });
                }
            }
        });
        
        // Bind filter events
        $filters.find('.filter-project').on('change', function() {
            me.filters.project = $(this).val() || null;
            me.refresh();
        });
        
        $filters.find('.filter-from-date').on('change', function() {
            me.filters.from_date = $(this).val() || null;
            me.refresh();
        });
        
        $filters.find('.filter-to-date').on('change', function() {
            me.filters.to_date = $(this).val() || null;
            me.refresh();
        });
        
        $filters.find('.filter-type').on('change', function() {
            me.filters.order_types = [];
            $filters.find('.filter-type:checked').each(function() {
                me.filters.order_types.push($(this).val());
            });
            me.refresh();
        });
    }
    
    refresh() {
        this.load_data();
    }
    
    load_data() {
        let me = this;
        
        frappe.call({
            method: 'plm_customizations.api.gantt_data.get_gantt_data',
            args: {
                project: this.filters.project,
                from_date: this.filters.from_date,
                to_date: this.filters.to_date,
                order_types: this.filters.order_types.join(',')
            },
            freeze: true,
            freeze_message: __('Loading...'),
            callback: (r) => {
                if (r.message && r.message.tasks) {
                    me.tasks = r.message.tasks;
                    me.render_gantt();
                }
            }
        });
    }
    
    render_gantt() {
        let $noData = this.page.main.find('.gantt-no-data');
        let $wrapper = this.page.main.find('.gantt-chart-wrapper');
        
        if (!this.tasks || this.tasks.length === 0) {
            $wrapper.hide();
            $noData.show();
            return;
        }
        
        $wrapper.show();
        $noData.hide();
        
        // Use table view for better detail display
        this.render_table_fallback();
    }
    
    render_table_fallback() {
        let $wrapper = this.page.main.find('.gantt-chart-wrapper');
        
        let html = `
            <table class="table table-bordered order-gantt-table">
                <thead>
                    <tr>
                        <th>${__('Order')}</th>
                        <th>${__('Type')}</th>
                        <th>${__('Planned/Est.')}</th>
                        <th>${__('Actual')}</th>
                        <th>${__('Required')}</th>
                        <th>${__('Delivered')}</th>
                        <th>${__('Progress')}</th>
                        <th>${__('Status')}</th>
                        <th>${__('Shipping/Start Delay')}</th>
                        <th>${__('Delivery/End Delay')}</th>
                    </tr>
                </thead>
                <tbody>
        `;
        
        this.tasks.forEach(task => {
            let row_class = '';
            if (task.status_color === 'delayed' || task.status_color === 'completed_late') {
                row_class = 'table-danger';
            } else if (task.status_color === 'at_risk') {
                row_class = 'table-warning';
            } else if (task.status_color === 'completed') {
                row_class = 'table-success';
            }
            
            let doctype_route = task.type === 'purchase' ? 'purchase-order' : 
                               task.type === 'work' ? 'work-order' : 'sales-order';
            
            let col1 = '-', col2 = '-', col3 = '-', col4 = '-';
            let delay1_html = '-', delay2_html = '-';
            
            if (task.type === 'work') {
                // Work Order: Planned Start/End vs Actual Start/End
                col1 = task.planned_start || '-';
                col2 = task.actual_start || '-';
                col3 = task.planned_end || '-';
                col4 = task.actual_end || '-';
                
                // Start delay
                if (task.start_delay_days !== undefined) {
                    if (task.start_delayed) {
                        delay1_html = `<span class="text-danger">+${task.start_delay_days}d</span>`;
                    } else if (task.start_delay_days < 0) {
                        delay1_html = `<span class="text-success">${task.start_delay_days}d</span>`;
                    } else if (task.actual_start) {
                        delay1_html = `<span class="text-success">On time</span>`;
                    }
                }
                
                // End delay
                if (task.end_delay_days !== undefined) {
                    if (task.end_delayed) {
                        delay2_html = `<span class="text-danger">+${task.end_delay_days}d</span>`;
                    } else if (task.end_delay_days < 0) {
                        delay2_html = `<span class="text-success">${task.end_delay_days}d</span>`;
                    } else if (task.progress >= 100) {
                        delay2_html = `<span class="text-success">On time</span>`;
                    }
                }
            } else if (task.type === 'sales') {
                // Sales Order: Est. Shipping vs Actual Shipping, Required vs Actual Delivery
                col1 = task.estimated_shipping || '-';
                col2 = task.actual_shipping || '-';
                col3 = task.customer_required_date || '-';
                col4 = task.actual_delivery || '-';
                
                // Shipping delay
                if (task.shipping_delay_days !== undefined) {
                    if (task.shipping_delayed) {
                        delay1_html = `<span class="text-danger">+${task.shipping_delay_days}d</span>`;
                    } else if (task.shipping_delay_days < 0) {
                        delay1_html = `<span class="text-success">${task.shipping_delay_days}d</span>`;
                    } else if (task.actual_shipping) {
                        delay1_html = `<span class="text-success">On time</span>`;
                    }
                }
                
                // Delivery delay
                if (task.delivery_delay_days !== undefined) {
                    if (task.delivery_delayed) {
                        delay2_html = `<span class="text-danger">+${task.delivery_delay_days}d</span>`;
                    } else if (task.delivery_delay_days < 0) {
                        delay2_html = `<span class="text-success">${task.delivery_delay_days}d</span>`;
                    } else if (task.progress >= 100) {
                        delay2_html = `<span class="text-success">On time</span>`;
                    }
                }
            } else if (task.type === 'purchase') {
                // Purchase Order: Order Date, ETA, Required By, Received
                col1 = task.start || '-';  // Order date
                col2 = task.end || '-';    // ETA or Schedule date
                col3 = task.required_date || '-';  // Required By
                col4 = task.progress >= 100 ? 'Received' : '-';
                
                // Arrival delay
                if (task.is_delayed) {
                    delay2_html = `<span class="text-danger">+${task.delay_days}d</span>`;
                } else if (task.delay_risk) {
                    delay2_html = `<span class="text-warning">ETA +${task.delay_days}d</span>`;
                } else if (task.progress >= 100) {
                    delay2_html = `<span class="text-success">On time</span>`;
                }
            }
            
            html += `
                <tr class="${row_class}">
                    <td><a href="/app/${doctype_route}/${task.id}">${task.name}</a></td>
                    <td><span class="badge badge-${task.type === 'purchase' ? 'info' : task.type === 'work' ? 'primary' : 'secondary'}">${task.type}</span></td>
                    <td>${this.format_date(col1)}</td>
                    <td>${this.format_date(col2)}</td>
                    <td>${this.format_date(col3)}</td>
                    <td>${this.format_date(col4)}</td>
                    <td>
                        <div class="progress" style="height: 20px; min-width: 60px;">
                            <div class="progress-bar ${task.progress >= 100 ? 'bg-success' : ''}" 
                                 role="progressbar" 
                                 style="width: ${task.progress}%">
                                ${task.progress.toFixed(0)}%
                            </div>
                        </div>
                    </td>
                    <td>${task.status}</td>
                    <td>${delay1_html}</td>
                    <td>${delay2_html}</td>
                </tr>
            `;
        });
        
        html += '</tbody></table>';
        
        $wrapper.html(html);
    }
    
    format_date(dateStr) {
        if (!dateStr || dateStr === '-' || dateStr === 'Received') return dateStr === 'Received' ? 'Received' : '-';
        // Remove time portion if present
        return dateStr.split(' ')[0];
    }
    
    render() {
        this.load_data();
    }
}
