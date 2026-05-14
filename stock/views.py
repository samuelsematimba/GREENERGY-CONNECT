from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from .models import (
    StockLevel, GoodsReceipt, GoodsReceiptItem,
    StockRequest, StockRequestItem,
    StockTransfer, StockTransferItem, WriteOff
)
from accounts.models import Location
from accounts.decorators import warehouse_or_above, outlet_or_above, admin_only, get_profile
from products.models import Product, SerializedItem


@login_required
def stock_dashboard(request):
    profile = get_profile(request.user)
    location = profile.location if profile else None
    role = profile.role.name if (profile and profile.role) else None

    if role in ('super_admin',):
        serialized = SerializedItem.objects.filter(status='in_stock').select_related('product', 'current_location')
        non_serialized = StockLevel.objects.filter(quantity__gt=0).select_related('product', 'location')
        in_transit = StockTransfer.objects.filter(status__in=['dispatched', 'in_transit'])
    elif role == 'country_admin' and profile.country:
        locs = Location.objects.filter(country=profile.country)
        serialized = SerializedItem.objects.filter(current_location__in=locs, status='in_stock').select_related('product', 'current_location')
        non_serialized = StockLevel.objects.filter(location__in=locs, quantity__gt=0).select_related('product', 'location')
        in_transit = StockTransfer.objects.filter(status__in=['dispatched', 'in_transit'], to_location__in=locs)
    elif role == 'warehouse_manager' and location:
        serialized = SerializedItem.objects.filter(current_location=location, status='in_stock').select_related('product')
        non_serialized = StockLevel.objects.filter(location=location, quantity__gt=0).select_related('product')
        in_transit = StockTransfer.objects.filter(from_location=location, status__in=['dispatched', 'in_transit'])
    elif location:
        serialized = SerializedItem.objects.filter(current_location=location, status='in_stock').select_related('product')
        non_serialized = StockLevel.objects.filter(location=location, quantity__gt=0).select_related('product')
        in_transit = StockTransfer.objects.filter(to_location=location, status__in=['dispatched', 'in_transit'])
    else:
        serialized = SerializedItem.objects.none()
        non_serialized = StockLevel.objects.none()
        in_transit = StockTransfer.objects.none()

    pending_requests = StockRequest.objects.filter(status='pending')
    if role == 'warehouse_manager' and location:
        pending_requests = pending_requests.filter(warehouse=location)
    elif role not in ('super_admin', 'country_admin'):
        pending_requests = StockRequest.objects.none()

    context = {
        'serialized': serialized,
        'non_serialized': non_serialized,
        'in_transit': in_transit,
        'location': location,
        'role': role,
        'pending_requests': pending_requests,
        'pending_count': pending_requests.count(),
    }
    return render(request, 'stock/dashboard.html', context)


@login_required
@warehouse_or_above
@warehouse_or_above
def goods_receipt_list(request):
    profile = get_profile(request.user)
    receipts = GoodsReceipt.objects.select_related('warehouse', 'received_by').order_by('-created_at')
    if profile.has_role('warehouse_manager') and profile.location:
        receipts = receipts.filter(warehouse=profile.location)
    elif profile.has_role('country_admin') and profile.country:
        receipts = receipts.filter(warehouse__country=profile.country)
    return render(request, 'stock/grn_list.html', {'receipts': receipts})


@login_required
@warehouse_or_above
@warehouse_or_above
def create_goods_receipt(request):
    profile = get_profile(request.user)
    if request.method == 'POST':
        warehouse_id = request.POST.get('warehouse')
        receipt_date = request.POST.get('receipt_date')
        notes = request.POST.get('notes', '')
        warehouse = get_object_or_404(Location, id=warehouse_id, location_type='warehouse')
        if profile.has_role('warehouse_manager') and profile.location != warehouse:
            messages.error(request, 'You can only receive stock at your assigned warehouse.')
            return redirect('stock:grn_list')
        grn = GoodsReceipt.objects.create(warehouse=warehouse, received_by=request.user, receipt_date=receipt_date, notes=notes)
        product_ids = request.POST.getlist('product_ids')
        quantities = request.POST.getlist('quantities')
        serial_lists = request.POST.getlist('serial_numbers')
        for pid, qty, serials in zip(product_ids, quantities, serial_lists):
            if not pid:
                continue
            product = Product.objects.get(id=pid)
            item = GoodsReceiptItem.objects.create(receipt=grn, product=product, quantity=int(qty) if qty else 0)
            if product.product_type == 'serialized' and serials:
                for s in serials.strip().splitlines():
                    s = s.strip().upper()
                    if s:
                        si, created = SerializedItem.objects.get_or_create(serial_number=s, defaults={'product': product, 'current_location': warehouse, 'status': 'in_stock'})
                        if not created:
                            si.current_location = warehouse
                            si.status = 'in_stock'
                            si.save()
                        item.serialized_items.add(si)
            else:
                level, _ = StockLevel.objects.get_or_create(product=product, location=warehouse)
                level.quantity += int(qty) if qty else 0
                level.save()
        messages.success(request, f'GRN {grn.grn_number} created. Stock updated at {warehouse.name}.')
        return redirect('stock:grn_list')
    if profile.has_role('warehouse_manager') and profile.location:
        warehouses = Location.objects.filter(id=profile.location.id)
    elif profile.has_role('country_admin') and profile.country:
        warehouses = Location.objects.filter(location_type='warehouse', country=profile.country)
    else:
        warehouses = Location.objects.filter(location_type='warehouse')
    return render(request, 'stock/create_grn.html', {'warehouses': warehouses, 'products': Product.objects.filter(is_active=True)})


@login_required
def request_list(request):
    profile = get_profile(request.user)
    role = profile.role.name if (profile and profile.role) else None
    qs = StockRequest.objects.select_related('outlet', 'warehouse', 'requested_by').order_by('-request_date')
    if role in ('outlet_manager', 'sales_agent') and profile.location:
        qs = qs.filter(outlet=profile.location)
    elif role == 'warehouse_manager' and profile.location:
        qs = qs.filter(warehouse=profile.location)
    elif role == 'country_admin' and profile.country:
        qs = qs.filter(outlet__country=profile.country)
    status_f = request.GET.get('status', '')
    if status_f:
        qs = qs.filter(status=status_f)
    return render(request, 'stock/request_list.html', {'requests': qs, 'status_filter': status_f, 'role': role})


@login_required
def create_stock_request(request):
    profile = get_profile(request.user)
    role = profile.role.name if (profile and profile.role) else None
    if role not in ('super_admin', 'country_admin', 'outlet_manager'):
        messages.error(request, 'Only Outlet Managers can create stock requests.')
        return redirect('stock:request_list')
    outlet = profile.location if (profile and profile.location and profile.location.location_type == 'outlet') else None
    if request.method == 'POST':
        outlet_id = request.POST.get('outlet') or (outlet.id if outlet else None)
        warehouse_id = request.POST.get('warehouse')
        notes = request.POST.get('notes', '')
        outlet_obj = get_object_or_404(Location, id=outlet_id, location_type='outlet')
        warehouse_obj = get_object_or_404(Location, id=warehouse_id, location_type='warehouse')
        if role == 'outlet_manager' and outlet_obj != profile.location:
            messages.error(request, 'You can only request stock for your own outlet.')
            return redirect('stock:request_list')
        if outlet_obj.country != warehouse_obj.country:
            messages.error(request, 'Warehouse must be in the same country as the outlet.')
            return redirect('stock:create_request')
        req = StockRequest.objects.create(outlet=outlet_obj, warehouse=warehouse_obj, requested_by=request.user, notes=notes, status='pending')
        added = 0
        for pid, qty in zip(request.POST.getlist('product_ids'), request.POST.getlist('quantities')):
            if pid and qty and int(qty) > 0:
                StockRequestItem.objects.create(request=req, product=Product.objects.get(id=pid), quantity_requested=int(qty))
                added += 1
        if added == 0:
            req.delete()
            messages.error(request, 'Add at least one product.')
            return redirect('stock:create_request')
        messages.success(request, f'Request {req.request_ref} submitted to {warehouse_obj.name}.')
        return redirect('stock:request_list')
    if outlet and outlet.affiliated_warehouse:
        warehouses = Location.objects.filter(id=outlet.affiliated_warehouse.id)
    elif profile.has_role('country_admin') and profile.country:
        warehouses = Location.objects.filter(location_type='warehouse', country=profile.country)
    else:
        warehouses = Location.objects.filter(location_type='warehouse')
    return render(request, 'stock/create_request.html', {'outlet': outlet, 'outlets': Location.objects.filter(location_type='outlet'), 'warehouses': warehouses, 'products': Product.objects.filter(is_active=True)})


@login_required
@warehouse_or_above
@warehouse_or_above
def review_request(request, pk):
    req = get_object_or_404(StockRequest, pk=pk)
    profile = get_profile(request.user)
    if profile.has_role('warehouse_manager') and profile.location != req.warehouse:
        messages.error(request, 'You can only review requests for your warehouse.')
        return redirect('stock:request_list')
    if req.status != 'pending':
        messages.warning(request, f'This request is already {req.get_status_display()}.')
        return redirect('stock:request_list')
    if request.method == 'POST':
        action = request.POST.get('action')
        req.reviewed_by = request.user
        if action == 'reject':
            req.status = 'rejected'
            req.rejection_reason = request.POST.get('rejection_reason', '')
            req.save()
            messages.warning(request, f'Request {req.request_ref} rejected.')
        elif action == 'approve':
            fully = True
            for item in req.items.all():
                aq = int(request.POST.get(f'approved_{item.id}', 0))
                item.quantity_approved = aq
                item.save()
                if aq < item.quantity_requested:
                    fully = False
            req.status = 'approved' if fully else 'partial'
            req.save()
            messages.success(request, f'Request {req.request_ref} approved. Ready to dispatch.')
        return redirect('stock:request_list')
    items_with_stock = []
    for item in req.items.all():
        if item.product.product_type == 'serialized':
            available = SerializedItem.objects.filter(product=item.product, current_location=req.warehouse, status='in_stock').count()
        else:
            sl = StockLevel.objects.filter(product=item.product, location=req.warehouse).first()
            available = sl.quantity if sl else 0
        items_with_stock.append({'item': item, 'available': available})
    return render(request, 'stock/review_request.html', {'req': req, 'items_with_stock': items_with_stock})


@login_required
@warehouse_or_above
@warehouse_or_above
def dispatch_transfer(request, req_pk):
    """Stock leaves warehouse here — deducted immediately on dispatch."""
    req = get_object_or_404(StockRequest, pk=req_pk, status__in=['approved', 'partial'])
    profile = get_profile(request.user)
    if profile.has_role('warehouse_manager') and profile.location != req.warehouse:
        messages.error(request, 'You can only dispatch from your own warehouse.')
        return redirect('stock:request_list')
    if request.method == 'POST':
        transfer = StockTransfer.objects.create(
            stock_request=req, from_location=req.warehouse, to_location=req.outlet,
            dispatched_by=request.user, dispatch_date=timezone.now(), status='dispatched'
        )
        errors = []
        for item in req.items.all():
            qty = item.quantity_approved or item.quantity_requested
            ti = StockTransferItem.objects.create(transfer=transfer, product=item.product, quantity_dispatched=qty)
            if item.product.product_type == 'serialized':
                scanned = 0
                for s in request.POST.get(f'serials_{item.id}', '').strip().splitlines():
                    s = s.strip().upper()
                    if not s:
                        continue
                    si = SerializedItem.objects.filter(serial_number=s, current_location=req.warehouse, status='in_stock').first()
                    if si:
                        si.status = 'in_transit'
                        si.save()
                        ti.serialized_items.add(si)
                        scanned += 1
                    else:
                        errors.append(f'Serial {s} not found in stock at this warehouse.')
                if scanned == 0:
                    errors.append(f'No valid serials scanned for {item.product.name}.')
            else:
                level = StockLevel.objects.filter(product=item.product, location=req.warehouse).first()
                if level and level.quantity >= qty:
                    level.quantity -= qty
                    level.save()
                else:
                    errors.append(f'Not enough stock for {item.product.name} (have {level.quantity if level else 0}, need {qty}).')
        if errors:
            transfer.delete()
            for e in errors:
                messages.error(request, e)
            return redirect('stock:dispatch', req_pk=req.pk)
        req.status = 'dispatched'
        req.save()
        messages.success(request, f'Transfer {transfer.transfer_ref} dispatched. Warehouse stock deducted.')
        return redirect('stock:request_list')
    items_for_dispatch = []
    for item in req.items.all():
        available = SerializedItem.objects.filter(product=item.product, current_location=req.warehouse, status='in_stock') if item.product.product_type == 'serialized' else []
        items_for_dispatch.append({'item': item, 'qty': item.quantity_approved or item.quantity_requested, 'available_serials': available})
    return render(request, 'stock/dispatch.html', {'req': req, 'items_for_dispatch': items_for_dispatch})


@login_required
def confirm_receipt(request, transfer_pk):
    """Stock arrives at outlet here — added to outlet stock on confirmation."""
    transfer = get_object_or_404(StockTransfer, pk=transfer_pk)
    profile = get_profile(request.user)
    role = profile.role.name if (profile and profile.role) else None
    if role not in ('super_admin', 'country_admin'):
        if not profile.location or profile.location != transfer.to_location:
            messages.error(request, 'You can only confirm receipt for your own outlet.')
            return redirect('stock:request_list')
    if transfer.status not in ('dispatched', 'in_transit'):
        messages.warning(request, 'Transfer already processed.')
        return redirect('stock:request_list')
    if request.method == 'POST':
        discrepancy = False
        for ti in transfer.items.all():
            qty_received = int(request.POST.get(f'received_{ti.id}', 0))
            ti.quantity_received = qty_received
            ti.save()
            if qty_received != ti.quantity_dispatched:
                discrepancy = True
            if ti.product.product_type == 'serialized':
                for si in ti.serialized_items.all():
                    si.status = 'in_stock'
                    si.current_location = transfer.to_location
                    si.save()
            else:
                level, _ = StockLevel.objects.get_or_create(product=ti.product, location=transfer.to_location)
                level.quantity += qty_received
                level.save()
        transfer.status = 'discrepancy' if discrepancy else 'received'
        transfer.receive_date = timezone.now()
        transfer.received_by = request.user
        if discrepancy:
            transfer.discrepancy_notes = request.POST.get('discrepancy_notes', '')
        transfer.save()
        transfer.stock_request.status = 'received'
        transfer.stock_request.save()
        if discrepancy:
            messages.warning(request, 'Receipt confirmed with discrepancy flagged.')
        else:
            messages.success(request, f'Receipt confirmed. Outlet stock at {transfer.to_location.name} updated.')
        return redirect('stock:request_list')
    return render(request, 'stock/confirm_receipt.html', {'transfer': transfer})


@login_required
@warehouse_or_above
def write_off_list(request):
    profile = get_profile(request.user)
    write_offs = WriteOff.objects.select_related('product', 'location', 'approved_by').order_by('-date')
    if profile.has_role('warehouse_manager') and profile.location:
        write_offs = write_offs.filter(location=profile.location)
    elif profile.has_role('country_admin') and profile.country:
        write_offs = write_offs.filter(location__country=profile.country)
    return render(request, 'stock/write_off_list.html', {'write_offs': write_offs})


@login_required
def stock_levels_detail(request):
    """
    Detailed stock levels page.
    - Super Admin / Country Admin: sees all locations with full breakdown
    - Warehouse Manager: sees their warehouse only
    - Outlet Manager / Sales Agent: sees their outlet only
    Supports drilldown into a specific location.
    """
    from django.db.models import Count, Sum, Q

    profile = get_profile(request.user)
    role = profile.role.name if (profile and profile.role) else None

    # ── Location scope based on role ──────────────────────────────────────────
    if role == 'super_admin':
        all_locations = Location.objects.all().order_by('location_type', 'name')
    elif role == 'country_admin' and profile.country:
        all_locations = Location.objects.filter(country=profile.country).order_by('location_type', 'name')
    elif role in ('warehouse_manager', 'outlet_manager', 'sales_agent') and profile.location:
        all_locations = Location.objects.filter(id=profile.location.id)
    else:
        all_locations = Location.objects.none()

    # ── Optional filter: drill into one location ───────────────────────────────
    selected_location_id = request.GET.get('location')
    location_type_filter = request.GET.get('type', '')  # 'warehouse' or 'outlet'
    selected_location = None

    if selected_location_id:
        selected_location = Location.objects.filter(id=selected_location_id).first()
        # Security — make sure this user can see this location
        if selected_location and selected_location not in all_locations:
            selected_location = None

    # ── Build location summary cards ──────────────────────────────────────────
    if location_type_filter:
        display_locations = all_locations.filter(location_type=location_type_filter)
    else:
        display_locations = all_locations

    location_summaries = []
    for loc in display_locations:
        serialized_count = SerializedItem.objects.filter(
            current_location=loc, status='in_stock'
        ).count()
        serialized_sold = SerializedItem.objects.filter(
            current_location=loc, status='sold'
        ).count()
        serialized_transit = SerializedItem.objects.filter(
            current_location=loc, status='in_transit'
        ).count()
        non_serialized_lines = StockLevel.objects.filter(
            location=loc, quantity__gt=0
        ).count()
        pending_requests = StockRequest.objects.filter(
            outlet=loc, status='pending'
        ).count() if loc.location_type == 'outlet' else 0
        in_transit_incoming = StockTransfer.objects.filter(
            to_location=loc, status__in=['dispatched', 'in_transit']
        ).count()

        location_summaries.append({
            'location': loc,
            'serialized_count': serialized_count,
            'serialized_sold': serialized_sold,
            'serialized_transit': serialized_transit,
            'non_serialized_lines': non_serialized_lines,
            'pending_requests': pending_requests,
            'in_transit_incoming': in_transit_incoming,
        })

    # ── Detail view for selected location ─────────────────────────────────────
    detail_serialized = []
    detail_non_serialized = []
    detail_in_transit = []
    detail_transfers = []
    total_in_stock = 0
    total_in_transit = 0
    total_faulty = 0   

    if selected_location:
        # Group serialized items by product
        from itertools import groupby
        serialized_items = SerializedItem.objects.filter(
            current_location=selected_location
        ).select_related('product').order_by('product__name', 'status')

        product_map = {}
        for item in serialized_items:
            key = item.product.id
            if key not in product_map:
                product_map[key] = {
                    'product': item.product,
                    'in_stock': [],
                    'in_transit': [],
                    'sold': [],
                    'faulty': [],
                    'other': [],
                }
            if item.status == 'in_stock':
                product_map[key]['in_stock'].append(item)
            elif item.status == 'in_transit':
                product_map[key]['in_transit'].append(item)
            elif item.status == 'sold':
                product_map[key]['sold'].append(item)
            elif item.status == 'faulty':
                product_map[key]['faulty'].append(item)
            else:
                product_map[key]['other'].append(item)
        detail_serialized = list(product_map.values())

        total_in_stock = sum(len(pg['in_stock']) for pg in detail_serialized)
        total_in_transit = sum(len(pg['in_transit']) for pg in detail_serialized)
        total_faulty = sum(len(pg['faulty']) for pg in detail_serialized)
        
        detail_non_serialized = StockLevel.objects.filter(
            location=selected_location
        ).select_related('product').order_by('product__name')

        detail_in_transit = StockTransfer.objects.filter(
            to_location=selected_location,
            status__in=['dispatched', 'in_transit']
        ).select_related('from_location').prefetch_related('items__product')

        detail_transfers = StockTransfer.objects.filter(
            Q(from_location=selected_location) | Q(to_location=selected_location)
        ).select_related('from_location', 'to_location').order_by('-dispatch_date')[:20]

    context = {
        'location_summaries': location_summaries,
        'all_locations': all_locations,
        'selected_location': selected_location,
        'detail_serialized': detail_serialized,
        'total_in_stock': total_in_stock,
        'total_in_transit': total_in_transit,
        'total_faulty': total_faulty,
        'detail_non_serialized': detail_non_serialized,
        'detail_in_transit': detail_in_transit,
        'detail_transfers': detail_transfers,
        'role': role,
        'location_type_filter': location_type_filter,
        'is_admin': role in ('super_admin', 'country_admin'),
    }
    return render(request, 'stock/stock_levels_detail.html', context)
