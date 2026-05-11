from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q, Sum
from .models import StockLevel, GoodsReceipt, GoodsReceiptItem, StockRequest, StockRequestItem, StockTransfer, StockTransferItem, WriteOff
from accounts.models import Location
from products.models import Product, SerializedItem


@login_required
def stock_dashboard(request):
    profile = getattr(request.user, 'userprofile', None)
    location = profile.location if profile else None

    if location:
        serialized = SerializedItem.objects.filter(current_location=location, status='in_stock').select_related('product')
        non_serialized = StockLevel.objects.filter(location=location, quantity__gt=0).select_related('product')
    else:
        serialized = SerializedItem.objects.filter(status='in_stock').select_related('product', 'current_location')
        non_serialized = StockLevel.objects.filter(quantity__gt=0).select_related('product', 'location')

    in_transit = StockTransfer.objects.filter(
        to_location=location, status__in=['dispatched', 'in_transit']
    ) if location else StockTransfer.objects.filter(status__in=['dispatched', 'in_transit'])

    context = {
        'serialized': serialized,
        'non_serialized': non_serialized,
        'in_transit': in_transit,
        'location': location,
    }
    return render(request, 'stock/dashboard.html', context)


@login_required
def goods_receipt_list(request):
    receipts = GoodsReceipt.objects.select_related('warehouse', 'received_by').order_by('-created_at')
    return render(request, 'stock/grn_list.html', {'receipts': receipts})


@login_required
def create_goods_receipt(request):
    if request.method == 'POST':
        warehouse_id = request.POST.get('warehouse')
        receipt_date = request.POST.get('receipt_date')
        notes = request.POST.get('notes', '')
        warehouse = get_object_or_404(Location, id=warehouse_id, location_type='warehouse')
        grn = GoodsReceipt.objects.create(
            warehouse=warehouse, received_by=request.user,
            receipt_date=receipt_date, notes=notes
        )
        product_ids = request.POST.getlist('product_ids')
        quantities = request.POST.getlist('quantities')
        serial_lists = request.POST.getlist('serial_numbers')

        for pid, qty, serials in zip(product_ids, quantities, serial_lists):
            if not pid:
                continue
            product = Product.objects.get(id=pid)
            item = GoodsReceiptItem.objects.create(
                receipt=grn, product=product,
                quantity=int(qty) if qty else 0
            )
            if product.product_type == 'serialized' and serials:
                for s in serials.strip().splitlines():
                    s = s.strip().upper()
                    if s:
                        si, created = SerializedItem.objects.get_or_create(
                            serial_number=s,
                            defaults={'product': product, 'current_location': warehouse}
                        )
                        if created:
                            item.serialized_items.add(si)
                        si.current_location = warehouse
                        si.status = 'in_stock'
                        si.save()
            else:
                level, _ = StockLevel.objects.get_or_create(product=product, location=warehouse)
                level.quantity += int(qty) if qty else 0
                level.save()

        messages.success(request, f'Goods Receipt {grn.grn_number} created.')
        return redirect('stock:grn_list')

    context = {
        'warehouses': Location.objects.filter(location_type='warehouse'),
        'products': Product.objects.filter(is_active=True),
    }
    return render(request, 'stock/create_grn.html', context)


@login_required
def request_list(request):
    profile = getattr(request.user, 'userprofile', None)
    requests = StockRequest.objects.select_related('outlet', 'warehouse', 'requested_by')
    if profile and profile.location:
        if profile.location.location_type == 'outlet':
            requests = requests.filter(outlet=profile.location)
        elif profile.location.location_type == 'warehouse':
            requests = requests.filter(warehouse=profile.location)
    status_filter = request.GET.get('status', '')
    if status_filter:
        requests = requests.filter(status=status_filter)
    context = {'requests': requests, 'status_filter': status_filter}
    return render(request, 'stock/request_list.html', context)


@login_required
def create_stock_request(request):
    profile = getattr(request.user, 'userprofile', None)
    outlet = profile.location if (profile and profile.location and profile.location.location_type == 'outlet') else None

    if request.method == 'POST':
        outlet_id = request.POST.get('outlet') or (outlet.id if outlet else None)
        warehouse_id = request.POST.get('warehouse')
        notes = request.POST.get('notes', '')
        outlet_obj = get_object_or_404(Location, id=outlet_id)
        warehouse_obj = get_object_or_404(Location, id=warehouse_id)
        req = StockRequest.objects.create(
            outlet=outlet_obj, warehouse=warehouse_obj,
            requested_by=request.user, notes=notes
        )
        product_ids = request.POST.getlist('product_ids')
        quantities = request.POST.getlist('quantities')
        for pid, qty in zip(product_ids, quantities):
            if pid and qty:
                StockRequestItem.objects.create(
                    request=req, product=Product.objects.get(id=pid),
                    quantity_requested=int(qty)
                )
        messages.success(request, f'Stock request {req.request_ref} submitted.')
        return redirect('stock:request_list')

    context = {
        'outlet': outlet,
        'outlets': Location.objects.filter(location_type='outlet'),
        'warehouses': Location.objects.filter(location_type='warehouse'),
        'products': Product.objects.filter(is_active=True),
    }
    return render(request, 'stock/create_request.html', context)


@login_required
def review_request(request, pk):
    req = get_object_or_404(StockRequest, pk=pk)
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'reject':
            req.status = 'rejected'
            req.rejection_reason = request.POST.get('rejection_reason', '')
            req.reviewed_by = request.user
            req.save()
            messages.warning(request, f'Request {req.request_ref} rejected.')
        elif action == 'approve':
            req.reviewed_by = request.user
            fully_approved = True
            for item in req.items.all():
                approved_qty = int(request.POST.get(f'approved_{item.id}', 0))
                item.quantity_approved = approved_qty
                item.save()
                if approved_qty < item.quantity_requested:
                    fully_approved = False
            req.status = 'approved' if fully_approved else 'partial'
            req.save()
            messages.success(request, f'Request {req.request_ref} approved.')
        return redirect('stock:request_list')
    return render(request, 'stock/review_request.html', {'req': req})


@login_required
def dispatch_transfer(request, req_pk):
    req = get_object_or_404(StockRequest, pk=req_pk, status__in=['approved', 'partial'])
    if request.method == 'POST':
        transfer = StockTransfer.objects.create(
            stock_request=req,
            from_location=req.warehouse,
            to_location=req.outlet,
            dispatched_by=request.user,
            status='dispatched'
        )
        for item in req.items.all():
            product = item.product
            ti = StockTransferItem.objects.create(
                transfer=transfer, product=product,
                quantity_dispatched=item.quantity_approved
            )
            if product.product_type == 'serialized':
                serial_input = request.POST.get(f'serials_{item.id}', '')
                for s in serial_input.strip().splitlines():
                    s = s.strip().upper()
                    si = SerializedItem.objects.filter(serial_number=s, current_location=req.warehouse, status='in_stock').first()
                    if si:
                        si.status = 'in_transit'
                        si.save()
                        ti.serialized_items.add(si)
            else:
                level = StockLevel.objects.filter(product=product, location=req.warehouse).first()
                if level:
                    level.quantity -= item.quantity_approved
                    level.save()
        req.status = 'dispatched'
        req.save()
        messages.success(request, f'Transfer {transfer.transfer_ref} dispatched.')
        return redirect('stock:request_list')
    return render(request, 'stock/dispatch.html', {'req': req})


@login_required
def confirm_receipt(request, transfer_pk):
    transfer = get_object_or_404(StockTransfer, pk=transfer_pk)
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
        messages.success(request, 'Receipt confirmed.' + (' Discrepancy flagged.' if discrepancy else ''))
        return redirect('stock:request_list')
    return render(request, 'stock/confirm_receipt.html', {'transfer': transfer})
