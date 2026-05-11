from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum
from django.http import HttpResponse
from .models import Sale, SaleItem, Customer
from accounts.models import Location
from products.models import Product, SerializedItem, Combo
import csv


@login_required
def sale_list(request):
    profile = getattr(request.user, 'userprofile', None)
    sales = Sale.objects.select_related('customer', 'outlet', 'agent').prefetch_related('items')

    if profile and profile.location and profile.location.location_type == 'outlet':
        sales = sales.filter(outlet=profile.location)

    q = request.GET.get('q', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    status = request.GET.get('status', '')
    payment = request.GET.get('payment', '')
    agent_id = request.GET.get('agent', '')

    if q:
        sales = sales.filter(Q(customer__full_name__icontains=q) | Q(sale_ref__icontains=q) | Q(customer__nin__icontains=q))
    if date_from:
        sales = sales.filter(sale_date__date__gte=date_from)
    if date_to:
        sales = sales.filter(sale_date__date__lte=date_to)
    if status:
        sales = sales.filter(status=status)
    if payment:
        sales = sales.filter(payment_method=payment)
    if agent_id:
        sales = sales.filter(agent_id=agent_id)

    total_revenue = sales.aggregate(total=Sum('total_amount'))['total'] or 0

    context = {
        'sales': sales.order_by('-sale_date'),
        'total_revenue': total_revenue,
        'q': q, 'date_from': date_from, 'date_to': date_to,
        'status': status, 'payment': payment,
    }
    return render(request, 'sales/sale_list.html', context)


@login_required
def create_sale(request):
    profile = getattr(request.user, 'userprofile', None)
    outlet = profile.location if (profile and profile.location and profile.location.location_type == 'outlet') else None

    if request.method == 'POST':
        # Customer data
        full_name = request.POST.get('full_name', '').strip().upper()
        nin = request.POST.get('nin', '').strip().upper()
        phone = request.POST.get('phone_number', '').strip()
        gender = request.POST.get('gender', '')
        village = request.POST.get('village', '').strip()
        district = request.POST.get('district', '').strip()
        national_id_photo = request.FILES.get('national_id_photo')

        # Validate NIN format (14 chars for Uganda)
        if len(nin) < 9:
            messages.error(request, 'Invalid NIN. Please check and try again.')
            return render(request, 'sales/create_sale.html', _sale_context(outlet))

        # Validate phone
        if len(phone) < 9:
            messages.error(request, 'Invalid phone number.')
            return render(request, 'sales/create_sale.html', _sale_context(outlet))

        customer, created = Customer.objects.get_or_create(
            nin=nin,
            defaults={
                'full_name': full_name, 'phone_number': phone,
                'gender': gender, 'village': village, 'district': district,
                'national_id_photo': national_id_photo,
            }
        )
        if not created:
            customer.full_name = full_name
            customer.phone_number = phone
            if national_id_photo:
                customer.national_id_photo = national_id_photo
            customer.save()

        outlet_id = request.POST.get('outlet') or (outlet.id if outlet else None)
        outlet_obj = get_object_or_404(Location, id=outlet_id)
        payment_method = request.POST.get('payment_method')
        amount_paid = request.POST.get('amount_paid', 0)
        notes = request.POST.get('notes', '')
        warranty = request.FILES.get('warranty_card')
        receipt_file = request.FILES.get('receipt_file')

        product_ids = request.POST.getlist('product_ids')
        combo_ids = request.POST.getlist('combo_ids')
        serial_numbers = request.POST.getlist('serial_numbers')
        quantities = request.POST.getlist('quantities')
        unit_prices = request.POST.getlist('unit_prices')

        total = sum(float(p) * int(q) for p, q in zip(unit_prices, quantities) if p and q)

        sale = Sale.objects.create(
            customer=customer, outlet=outlet_obj, agent=request.user,
            payment_method=payment_method, total_amount=total,
            amount_paid=float(amount_paid), notes=notes,
            warranty_card=warranty, receipt_file=receipt_file,
            status='completed' if float(amount_paid) >= total else 'pending_payment'
        )

        for pid, sn, qty, price in zip(product_ids, serial_numbers, quantities, unit_prices):
            if pid and price:
                product = Product.objects.get(id=pid)
                si = SerializedItem.objects.filter(serial_number=sn.strip().upper()).first() if sn.strip() else None
                SaleItem.objects.create(
                    sale=sale, product=product,
                    serialized_item=si, quantity=int(qty),
                    unit_price=float(price)
                )
                if si:
                    si.status = 'sold'
                    si.save()

        for cid, qty, price in zip(combo_ids, quantities, unit_prices):
            if cid and price:
                SaleItem.objects.create(
                    sale=sale, combo=Combo.objects.get(id=cid),
                    quantity=int(qty), unit_price=float(price)
                )

        messages.success(request, f'Sale {sale.sale_ref} recorded successfully.')
        return redirect('sales:sale_detail', pk=sale.pk)

    return render(request, 'sales/create_sale.html', _sale_context(outlet))


def _sale_context(outlet):
    return {
        'outlet': outlet,
        'outlets': Location.objects.filter(location_type='outlet'),
        'products': Product.objects.filter(is_active=True),
        'combos': Combo.objects.filter(is_active=True),
    }


@login_required
def sale_detail(request, pk):
    sale = get_object_or_404(Sale, pk=pk)
    return render(request, 'sales/sale_detail.html', {'sale': sale})


@login_required
def customer_list(request):
    customers = Customer.objects.all()
    q = request.GET.get('q', '')
    if q:
        customers = customers.filter(Q(full_name__icontains=q) | Q(nin__icontains=q) | Q(phone_number__icontains=q))
    return render(request, 'sales/customer_list.html', {'customers': customers, 'q': q})


@login_required
def scan_qr_sale(request):
    """Look up a serialized item by serial number for sale."""
    if request.method == 'POST':
        serial = request.POST.get('serial', '').strip().upper()
        item = SerializedItem.objects.filter(serial_number=serial).select_related('product', 'current_location').first()
        if item:
            return render(request, 'sales/scan_qr.html', {'item': item, 'serial': serial})
        messages.error(request, f'No item found with serial number {serial}')
    return render(request, 'sales/scan_qr.html', {})


@login_required
def export_sales_csv(request):
    profile = getattr(request.user, 'userprofile', None)
    sales = Sale.objects.select_related('customer', 'outlet', 'agent')
    if profile and profile.location and profile.location.location_type == 'outlet':
        sales = sales.filter(outlet=profile.location)

    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    if date_from:
        sales = sales.filter(sale_date__date__gte=date_from)
    if date_to:
        sales = sales.filter(sale_date__date__lte=date_to)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="sales_export.csv"'
    writer = csv.writer(response)
    writer.writerow(['Sale Ref', 'Date', 'Customer', 'NIN', 'Phone', 'Outlet', 'Agent', 'Payment Method', 'Total', 'Paid', 'Balance', 'Status'])
    for s in sales:
        writer.writerow([
            s.sale_ref, s.sale_date.strftime('%Y-%m-%d %H:%M'),
            s.customer.full_name, s.customer.nin, s.customer.phone_number,
            s.outlet.name, s.agent.get_full_name() if s.agent else '',
            s.get_payment_method_display(), s.total_amount,
            s.amount_paid, s.balance, s.get_status_display()
        ])
    return response
