import frappe
from frappe import _
from frappe.utils import getdate, today, date_diff, flt


@frappe.whitelist()
def get_gantt_data(project=None, from_date=None, to_date=None, order_types=None):
    """
    Get Gantt chart data for Purchase Orders, Work Orders, and Sales Orders.
    
    Args:
        project: Filter by project
        from_date: Start date filter
        to_date: End date filter
        order_types: Comma-separated list of order types to include (purchase,work,sales)
    
    Returns:
        dict with tasks list for Gantt chart
    """
    tasks = []
    
    # Parse order types
    if order_types:
        types_list = [t.strip() for t in order_types.split(",")]
    else:
        types_list = ["purchase", "work", "sales"]
    
    # Get Purchase Orders
    if "purchase" in types_list:
        tasks.extend(get_purchase_order_tasks(project, from_date, to_date))
    
    # Get Work Orders
    if "work" in types_list:
        tasks.extend(get_work_order_tasks(project, from_date, to_date))
    
    # Get Sales Orders
    if "sales" in types_list:
        tasks.extend(get_sales_order_tasks(project, from_date, to_date))
    
    return {"tasks": tasks}


def get_purchase_order_tasks(project=None, from_date=None, to_date=None):
    """Get Purchase Order tasks for Gantt chart"""
    tasks = []
    
    filters = {"docstatus": ["in", [0, 1]]}
    if project:
        filters["project"] = project
    
    orders = frappe.get_all(
        "Purchase Order",
        filters=filters,
        fields=[
            "name", "supplier_name", "transaction_date", "schedule_date",
            "eta_date", "per_received", "status", "project"
        ],
        order_by="schedule_date"
    )
    
    today_date = getdate(today())
    
    for order in orders:
        start_date = order.transaction_date or today_date
        # Use ETA if available, otherwise use schedule_date
        end_date = order.eta_date or order.schedule_date or start_date
        required_date = order.schedule_date
        
        # Apply date filter
        if from_date and getdate(end_date) < getdate(from_date):
            continue
        if to_date and getdate(start_date) > getdate(to_date):
            continue
        
        # Calculate delay
        is_delayed = False
        delay_days = 0
        delay_risk = False
        
        if required_date:
            if order.per_received < 100 and today_date > getdate(required_date):
                is_delayed = True
                delay_days = date_diff(today_date, required_date)
            elif order.eta_date and getdate(order.eta_date) > getdate(required_date):
                delay_risk = True
                delay_days = date_diff(order.eta_date, required_date)
        
        # Determine status color
        if order.per_received >= 100:
            status_color = "completed"
        elif is_delayed:
            status_color = "delayed"
        elif delay_risk:
            status_color = "at_risk"
        else:
            status_color = "normal"
        
        tasks.append({
            "id": order.name,
            "name": f"PO: {order.supplier_name or order.name}",
            "type": "purchase",
            "start": str(start_date),
            "end": str(end_date),
            "required_date": str(required_date) if required_date else None,
            "progress": flt(order.per_received),
            "dependencies": [],
            "is_delayed": is_delayed,
            "delay_risk": delay_risk,
            "delay_days": delay_days,
            "status": order.status,
            "status_color": status_color,
            "project": order.project
        })
    
    return tasks


def get_work_order_tasks(project=None, from_date=None, to_date=None):
    """Get Work Order tasks for Gantt chart"""
    tasks = []
    
    filters = {"docstatus": ["in", [0, 1]]}
    if project:
        filters["project"] = project
    
    orders = frappe.get_all(
        "Work Order",
        filters=filters,
        fields=[
            "name", "production_item", "item_name", "planned_start_date", 
            "planned_end_date", "expected_delivery_date", "actual_start_date",
            "actual_end_date", "qty", "produced_qty", "status", "project"
        ],
        order_by="planned_start_date"
    )
    
    today_date = getdate(today())
    
    for order in orders:
        # Planned dates
        planned_start = order.planned_start_date
        planned_end = order.planned_end_date or order.expected_delivery_date
        
        # Actual dates
        actual_start = order.actual_start_date
        actual_end = order.actual_end_date
        
        # For display: use actual if available, otherwise planned
        start_date = actual_start or planned_start or today_date
        end_date = actual_end or planned_end or start_date
        
        # Apply date filter
        if from_date and getdate(end_date) < getdate(from_date):
            continue
        if to_date and getdate(start_date) > getdate(to_date):
            continue
        
        # Calculate progress
        progress = 0
        if order.qty and order.qty > 0:
            progress = flt(order.produced_qty / order.qty * 100, 2)
        
        # Calculate start delay (actual_start vs planned_start)
        start_delay_days = 0
        start_delayed = False
        if planned_start:
            if actual_start:
                # Started: compare actual start with planned start
                start_delay_days = date_diff(getdate(actual_start), getdate(planned_start))
                start_delayed = start_delay_days > 0
            elif today_date > getdate(planned_start):
                # Not started yet but should have started
                start_delay_days = date_diff(today_date, getdate(planned_start))
                start_delayed = True
        
        # Calculate end delay (actual_end or projected end vs planned_end)
        end_delay_days = 0
        end_delayed = False
        if planned_end:
            if progress >= 100 and actual_end:
                # Completed: compare actual end with planned end
                end_delay_days = date_diff(getdate(actual_end), getdate(planned_end))
                end_delayed = end_delay_days > 0
            elif progress < 100 and today_date > getdate(planned_end):
                # Not completed but past planned end date
                end_delay_days = date_diff(today_date, getdate(planned_end))
                end_delayed = True
        
        # Overall delay status
        is_delayed = start_delayed or end_delayed
        delay_days = max(start_delay_days, end_delay_days)
        
        # Get dependencies
        dependencies = get_order_dependencies("Work Order", order.name)
        
        # Determine status color
        if progress >= 100:
            if end_delayed:
                status_color = "completed_late"  # Completed but was late
            else:
                status_color = "completed"
        elif end_delayed:
            status_color = "delayed"
        elif start_delayed:
            status_color = "at_risk"
        else:
            status_color = "normal"
        
        tasks.append({
            "id": order.name,
            "name": f"WO: {order.item_name or order.production_item}",
            "type": "work",
            "start": str(start_date),
            "end": str(end_date),
            "progress": progress,
            "dependencies": dependencies,
            "is_delayed": is_delayed,
            "delay_days": delay_days,
            "status": order.status,
            "status_color": status_color,
            "project": order.project,
            # Planned vs Actual details
            "planned_start": str(planned_start) if planned_start else None,
            "planned_end": str(planned_end) if planned_end else None,
            "actual_start": str(actual_start) if actual_start else None,
            "actual_end": str(actual_end) if actual_end else None,
            "start_delay_days": start_delay_days,
            "end_delay_days": end_delay_days,
            "start_delayed": start_delayed,
            "end_delayed": end_delayed
        })
    
    return tasks


def get_sales_order_tasks(project=None, from_date=None, to_date=None):
    """Get Sales Order tasks for Gantt chart"""
    tasks = []
    
    filters = {"docstatus": ["in", [0, 1]]}
    if project:
        filters["project"] = project
    
    orders = frappe.get_all(
        "Sales Order",
        filters=filters,
        fields=[
            "name", "customer_name", "transaction_date", "delivery_date",
            "estimated_shipping_date", "actual_shipping_date", "actual_delivery_date",
            "per_delivered", "status", "delivery_status", "project"
        ],
        order_by="delivery_date"
    )
    
    today_date = getdate(today())
    
    for order in orders:
        # Dates
        order_date = order.transaction_date or today_date
        customer_required_date = order.delivery_date  # Customer's required delivery date
        estimated_shipping = order.estimated_shipping_date
        actual_shipping = order.actual_shipping_date
        actual_delivery = order.actual_delivery_date
        
        # For display timeline
        start_date = order_date
        end_date = actual_delivery or customer_required_date or start_date
        
        # Apply date filter
        if from_date and getdate(end_date) < getdate(from_date):
            continue
        if to_date and getdate(start_date) > getdate(to_date):
            continue
        
        # Calculate shipping delay (actual_shipping vs estimated_shipping)
        shipping_delay_days = 0
        shipping_delayed = False
        if estimated_shipping:
            if actual_shipping:
                shipping_delay_days = date_diff(getdate(actual_shipping), getdate(estimated_shipping))
                shipping_delayed = shipping_delay_days > 0
            elif today_date > getdate(estimated_shipping):
                # Not shipped yet but past estimated shipping date
                shipping_delay_days = date_diff(today_date, getdate(estimated_shipping))
                shipping_delayed = True
        
        # Calculate delivery delay (actual_delivery vs customer_required_date)
        delivery_delay_days = 0
        delivery_delayed = False
        if customer_required_date:
            if actual_delivery:
                # Delivered: compare actual delivery with customer required date
                delivery_delay_days = date_diff(getdate(actual_delivery), getdate(customer_required_date))
                delivery_delayed = delivery_delay_days > 0
            elif order.per_delivered < 100 and today_date > getdate(customer_required_date):
                # Not delivered but past required date
                delivery_delay_days = date_diff(today_date, getdate(customer_required_date))
                delivery_delayed = True
        
        # Overall delay status
        is_delayed = shipping_delayed or delivery_delayed
        delay_days = max(shipping_delay_days, delivery_delay_days)
        
        # Get dependencies
        dependencies = get_order_dependencies("Sales Order", order.name)
        
        # Determine status color
        if order.per_delivered >= 100:
            if delivery_delayed:
                status_color = "completed_late"
            else:
                status_color = "completed"
        elif delivery_delayed:
            status_color = "delayed"
        elif shipping_delayed:
            status_color = "at_risk"
        else:
            status_color = "normal"
        
        tasks.append({
            "id": order.name,
            "name": f"SO: {order.customer_name or order.name}",
            "type": "sales",
            "start": str(start_date),
            "end": str(end_date),
            "progress": flt(order.per_delivered),
            "dependencies": dependencies,
            "is_delayed": is_delayed,
            "delay_days": delay_days,
            "status": order.status,
            "status_color": status_color,
            "project": order.project,
            # Shipping and delivery details
            "estimated_shipping": str(estimated_shipping) if estimated_shipping else None,
            "actual_shipping": str(actual_shipping) if actual_shipping else None,
            "customer_required_date": str(customer_required_date) if customer_required_date else None,
            "actual_delivery": str(actual_delivery) if actual_delivery else None,
            "shipping_delay_days": shipping_delay_days,
            "delivery_delay_days": delivery_delay_days,
            "shipping_delayed": shipping_delayed,
            "delivery_delayed": delivery_delayed
        })
    
    return tasks


def get_order_dependencies(parent_doctype, parent_name):
    """Get dependencies for an order from Order Dependency child table"""
    dependencies = []
    
    try:
        deps = frappe.get_all(
            "Order Dependency",
            filters={"parent": parent_name, "parenttype": parent_doctype},
            fields=["order_name"]
        )
        dependencies = [d.order_name for d in deps if d.order_name]
    except Exception:
        pass
    
    return dependencies


@frappe.whitelist()
def get_projects():
    """Get list of projects for filter dropdown"""
    projects = frappe.get_all(
        "Project",
        filters={"status": ["not in", ["Cancelled", "Completed"]]},
        fields=["name", "project_name"],
        order_by="project_name"
    )
    return projects


@frappe.whitelist()
def get_order_details(order_id, order_type):
    """Get detailed information about an order"""
    if order_type == "purchase":
        return frappe.get_doc("Purchase Order", order_id).as_dict()
    elif order_type == "work":
        return frappe.get_doc("Work Order", order_id).as_dict()
    elif order_type == "sales":
        return frappe.get_doc("Sales Order", order_id).as_dict()
    return None
