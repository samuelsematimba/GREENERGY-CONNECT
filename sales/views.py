from accounts.decorators import sales_or_above, admin_only, get_profile
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum, Count
from django.http import HttpResponse, JsonResponse
from .models import Sale, SaleItem, Customer
from accounts.models import Location
from products.models import Product, SerializedItem, Combo
import csv, io


# ─── CUSTOMER SEARCH AJAX ─────────────────────────────────────────────────────

@login_required
def customer_search_ajax(request):
    """
    AJAX endpoint — search customers by name, phone or NIN across ALL locations.
    Used by the sale form to find existing customers before creating new ones.
    """
    q = request.GET.get('q', '').strip()
    if len(q) < 2:
        return JsonResponse({'customers': []})
    customers = Customer.objects.filter(
        Q(full_name__icontains=q) |
        Q(phone_number__icontains=q) |
        Q(nin__icontains=q)
    ).select_related('registered_at')[:10]
    data = []
    for c in customers:
        data.append({
            'id': c.id,
            'full_name': c.full_name,
            'nin': c.nin,
            'phone_number': c.phone_number,
            'gender': c.get_gender_display(),
            'village': c.village,
            'district': c.district,
            'registered_at': c.registered_at.name if c.registered_at else '—',
            'sales_count': c.sales.count(),
        })
    return JsonResponse({'customers': data})


# ─── CUSTOMER MANAGEMENT ──────────────────────────────────────────────────────

@login_required
@sales_or_above
def customer_list(request):
    profile = get_profile(request.user)
    role = profile.role.name if (profile and profile.role) else None

    # Admins see all customers with location breakdown
    # Outlet users see only customers registered at their outlet
    if role in ('super_admin', 'country_admin'):
        customers = Customer.objects.select_related('registered_at').all()
        # Location summary for admins
        location_summary = Customer.objects.values(
            'registered_at__name', 'registered_at__id'
        ).annotate(total=Count('id')).order_by('-total')
        show_location_summary = True
    elif profile and profile.location:
        customers = Customer.objects.filter(
            registered_at=profile.location
        ).select_related('registered_at')
        location_summary = []
        show_location_summary = False
    else:
        customers = Customer.objects.none()
        location_summary = []
        show_location_summary = False

    q = request.GET.get('q', '')
    location_filter = request.GET.get('location', '')
    if q:
        customers = customers.filter(
            Q(full_name__icontains=q) |
            Q(nin__icontains=q) |
            Q(phone_number__icontains=q)
        )
    if location_filter and role in ('super_admin', 'country_admin'):
        customers = customers.filter(registered_at_id=location_filter)

    return render(request, 'sales/customer_list.html', {
        'customers': customers.order_by('full_name'),
        'location_summary': location_summary,
        'show_location_summary': show_location_summary,
        'locations': Location.objects.filter(location_type='outlet') if show_location_summary else [],
        'q': q,
        'location_filter': location_filter,
        'total': customers.count(),
    })


@login_required
@sales_or_above
def create_customer(request):
    """Standalone customer creation — used before making a sale."""
    profile = get_profile(request.user)
    outlet = profile.location if (profile and profile.location and profile.location.location_type == 'outlet') else None

    if request.method == 'POST':
        full_name = request.POST.get('full_name', '').strip().upper()
        nin = request.POST.get('nin', '').strip().upper()
        phone = request.POST.get('phone_number', '').strip()
        gender = request.POST.get('gender', '')
        village = request.POST.get('village', '').strip()
        district = request.POST.get('district', '').strip()
        national_id_photo = request.FILES.get('national_id_photo')
        registered_at_id = request.POST.get('registered_at') or (outlet.id if outlet else None)

        errors = []
        if len(nin) < 9:
            errors.append('Invalid NIN — must be at least 9 characters.')
        if len(phone) < 9:
            errors.append('Invalid phone number.')
        if not full_name:
            errors.append('Full name is required.')

        # Check for duplicates across ALL locations
        existing_nin = Customer.objects.filter(nin=nin).first()
        existing_phone = Customer.objects.filter(phone_number=phone).first()

        if existing_nin:
            messages.warning(request, f'A customer with NIN {nin} already exists: {existing_nin.full_name}. Redirecting to their profile.')
            return redirect('sales:customer_detail', pk=existing_nin.pk)

        if existing_phone:
            messages.warning(request, f'A customer with phone {phone} already exists: {existing_phone.full_name}. Redirecting to their profile.')
            return redirect('sales:customer_detail', pk=existing_phone.pk)

        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, 'sales/create_customer.html', {
                'outlets': Location.objects.filter(location_type='outlet'),
                'outlet': outlet,
            })

        registered_at = Location.objects.filter(id=registered_at_id).first()
        customer = Customer.objects.create(
            full_name=full_name, nin=nin, phone_number=phone,
            gender=gender, village=village, district=district,
            national_id_photo=national_id_photo,
            registered_at=registered_at,
        )
        messages.success(request, f'Customer {customer.full_name} created successfully.')

        # If coming from sale flow, redirect back to sale with customer pre-filled
        next_url = request.POST.get('next', '')
        if next_url == 'sale':
            return redirect(f"{__import__('django.urls', fromlist=['reverse']).reverse('sales:create_sale')}?customer_id={customer.pk}")
        return redirect('sales:customer_detail', pk=customer.pk)

    return render(request, 'sales/create_customer.html', {
        'outlets': Location.objects.filter(location_type='outlet'),
        'outlet': outlet,
    })


@login_required
@sales_or_above
def customer_detail(request, pk):
    profile = get_profile(request.user)
    role = profile.role.name if (profile and profile.role) else None
    customer = get_object_or_404(Customer, pk=pk)

    # Outlet users can only see customers from their outlet
    if role not in ('super_admin', 'country_admin'):
        if profile.location and customer.registered_at != profile.location:
            messages.error(request, 'You do not have access to this customer.')
            return redirect('sales:customer_list')

    sales = customer.sales.select_related('outlet', 'agent').prefetch_related('items').order_by('-sale_date')
    return render(request, 'sales/customer_detail.html', {
        'customer': customer,
        'sales': sales,
        'total_spent': sales.aggregate(t=Sum('total_amount'))['t'] or 0,
    })


@login_required
@admin_only
def bulk_upload_customers(request):
    """Admin: upload customers via CSV."""
    if request.method == 'POST':
        csv_file = request.FILES.get('csv_file')
        if not csv_file:
            messages.error(request, 'Please upload a CSV file.')
            return redirect('sales:bulk_upload_customers')

        if not csv_file.name.endswith('.csv'):
            messages.error(request, 'File must be a .csv file.')
            return redirect('sales:bulk_upload_customers')

        decoded = csv_file.read().decode('utf-8')
        reader = csv.DictReader(io.StringIO(decoded))

        created = 0
        skipped = 0
        errors = []

        for i, row in enumerate(reader, start=2):
            try:
                nin = row.get('nin', '').strip().upper()
                phone = row.get('phone_number', '').strip()
                full_name = row.get('full_name', '').strip().upper()
                outlet_name = row.get('outlet', '').strip()

                if not nin or not phone or not full_name:
                    errors.append(f'Row {i}: Missing required fields (full_name, nin, phone_number).')
                    skipped += 1
                    continue

                if Customer.objects.filter(Q(nin=nin) | Q(phone_number=phone)).exists():
                    skipped += 1
                    continue

                registered_at = Location.objects.filter(
                    name__iexact=outlet_name, location_type='outlet'
                ).first() if outlet_name else None

                Customer.objects.create(
                    full_name=full_name, nin=nin, phone_number=phone,
                    gender=row.get('gender', '').strip()[:1].upper(),
                    village=row.get('village', '').strip(),
                    district=row.get('district', '').strip(),
                    registered_at=registered_at,
                )
                created += 1
            except Exception as e:
                errors.append(f'Row {i}: {str(e)}')
                skipped += 1

        messages.success(request, f'{created} customers imported. {skipped} skipped (duplicates or errors).')
        if errors:
            for e in errors[:5]:
                messages.warning(request, e)
        return redirect('sales:customer_list')

    # Show CSV template download
    sample_headers = ['full_name', 'nin', 'phone_number', 'gender', 'village', 'district', 'outlet']
    return render(request, 'sales/bulk_upload_customers.html', {
        'sample_headers': sample_headers,
        'outlets': Location.objects.filter(location_type='outlet'),
    })


@login_required
@admin_only
def download_customer_template(request):
    """Download a blank CSV template for bulk upload."""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="customer_upload_template.csv"'
    writer = csv.writer(response)
    writer.writerow(['full_name', 'nin', 'phone_number', 'gender', 'village', 'district', 'outlet'])
    writer.writerow(['JOHN EXAMPLE DOE', 'CM90012345678AB', '0701234567', 'M', 'Kampala Central', 'Kampala', 'Kampala Outlet'])
    return response


# ─── SALES ────────────────────────────────────────────────────────────────────

@login_required
@sales_or_above
def sale_list(request):
    profile = get_profile(request.user)
    sales = Sale.objects.select_related('customer', 'outlet', 'agent').prefetch_related('items')

    if profile and profile.location and profile.location.location_type == 'outlet':
        sales = sales.filter(outlet=profile.location)

    q = request.GET.get('q', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    status = request.GET.get('status', '')
    payment = request.GET.get('payment', '')

    if q:
        sales = sales.filter(
            Q(customer__full_name__icontains=q) |
            Q(sale_ref__icontains=q) |
            Q(customer__nin__icontains=q)
        )
    if date_from:
        sales = sales.filter(sale_date__date__gte=date_from)
    if date_to:
        sales = sales.filter(sale_date__date__lte=date_to)
    if status:
        sales = sales.filter(status=status)
    if payment:
        sales = sales.filter(payment_method=payment)

    total_revenue = sales.aggregate(total=Sum('total_amount'))['total'] or 0

    return render(request, 'sales/sale_list.html', {
        'sales': sales.order_by('-sale_date'),
        'total_revenue': total_revenue,
        'q': q, 'date_from': date_from, 'date_to': date_to,
        'status': status, 'payment': payment,
    })


@login_required
@sales_or_above
def create_sale(request):
    profile = get_profile(request.user)
    outlet = profile.location if (profile and profile.location and profile.location.location_type == 'outlet') else None

    # Pre-fill customer if coming from customer detail page
    preselected_customer = None
    customer_id = request.GET.get('customer_id')
    if customer_id:
        preselected_customer = Customer.objects.filter(pk=customer_id).first()

    if request.method == 'POST':
        customer_id_post = request.POST.get('customer_id', '').strip()
        customer = Customer.objects.filter(pk=customer_id_post).first() if customer_id_post else None

        if not customer:
            messages.error(request, 'Please search and select a customer before completing the sale.')
            ctx = _sale_context(outlet)
            ctx['preselected_customer'] = preselected_customer
            return render(request, 'sales/create_sale.html', ctx)

        outlet_id = request.POST.get('outlet') or (outlet.id if outlet else None)
        outlet_obj = get_object_or_404(Location, id=outlet_id)
        payment_method = request.POST.get('payment_method')
        amount_paid = request.POST.get('amount_paid', 0) or 0
        notes = request.POST.get('notes', '')
        warranty = request.FILES.get('warranty_card')
        receipt_file = request.FILES.get('receipt_file')

        product_ids = request.POST.getlist('product_ids')
        combo_ids = request.POST.getlist('combo_ids')
        serial_numbers = request.POST.getlist('serial_numbers')
        quantities = request.POST.getlist('quantities')
        unit_prices = request.POST.getlist('unit_prices')

        if not any(pid for pid in product_ids) and not any(cid for cid in combo_ids):
            messages.error(request, 'Please add at least one product or combo to the sale.')
            ctx = _sale_context(outlet)
            ctx['preselected_customer'] = customer
            return render(request, 'sales/create_sale.html', ctx)

        total = sum(
            float(p) * int(q) for p, q in zip(unit_prices, quantities)
            if p and q
        )
        subsidy_discount = float(request.POST.get('subsidy_discount', 0) or 0)
        total = max(0, total - subsidy_discount)

        sale = Sale.objects.create(
            customer=customer, outlet=outlet_obj, agent=request.user,
            payment_method=payment_method, total_amount=total,
            amount_paid=float(amount_paid),
            notes=notes, warranty_card=warranty, receipt_file=receipt_file,
            status='completed' if float(amount_paid) >= total else 'pending_payment'
        )

        # Attach subsidy
        subsidy_id = request.POST.get('subsidy_id')
        if subsidy_id:
            from products.models import Subsidy
            try:
                sale.subsidy = Subsidy.objects.get(id=subsidy_id)
                sale.subsidy_discount_applied = subsidy_discount
                sale.save()
            except Subsidy.DoesNotExist:
                pass

        # Save product items
        for pid, sn, qty, price in zip(product_ids, serial_numbers, quantities, unit_prices):
            if pid and price:
                product = Product.objects.get(id=pid)
                si = SerializedItem.objects.filter(
                    serial_number=sn.strip().upper()
                ).first() if sn.strip() else None
                SaleItem.objects.create(
                    sale=sale, product=product,
                    serialized_item=si, quantity=int(qty),
                    unit_price=float(price)
                )
                if si:
                    si.status = 'sold'
                    si.save()

        # Save combo items
        for cid, qty, price in zip(combo_ids, quantities, unit_prices):
            if cid and price:
                SaleItem.objects.create(
                    sale=sale, combo=Combo.objects.get(id=cid),
                    quantity=int(qty), unit_price=float(price)
                )

        messages.success(request, f'Sale {sale.sale_ref} recorded successfully.')
        return redirect('sales:sale_detail', pk=sale.pk)

    ctx = _sale_context(outlet)
    ctx['preselected_customer'] = preselected_customer
    return render(request, 'sales/create_sale.html', ctx)


def _sale_context(outlet):
    from products.models import Subsidy
    from django.utils.timezone import now
    from django.db.models import Q as DQ
    today = now().date()
    subsidies = Subsidy.objects.filter(status='active').filter(
        DQ(valid_from__isnull=True) | DQ(valid_from__lte=today)
    ).filter(
        DQ(valid_to__isnull=True) | DQ(valid_to__gte=today)
    ).prefetch_related('outlets', 'products')
    return {
        'outlet': outlet,
        'outlets': Location.objects.filter(location_type='outlet'),
        'products': Product.objects.filter(is_active=True).select_related('category'),
        'combos': Combo.objects.filter(is_active=True),
        'subsidies': subsidies,
        'preselected_customer': None,
    }


@login_required
@sales_or_above
def sale_detail(request, pk):
    sale = get_object_or_404(Sale, pk=pk)
    return render(request, 'sales/sale_detail.html', {'sale': sale})


@login_required
@sales_or_above
def scan_qr_sale(request):
    if request.method == 'POST':
        serial = request.POST.get('serial', '').strip().upper()
        item = SerializedItem.objects.filter(serial_number=serial).select_related('product', 'current_location').first()
        if item:
            return render(request, 'sales/scan_qr.html', {'item': item, 'serial': serial})
        messages.error(request, f'No item found with serial number {serial}')
    return render(request, 'sales/scan_qr.html', {})


@login_required
@sales_or_above
def export_sales_csv(request):
    profile = get_profile(request.user)
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
    writer.writerow(['Sale Ref', 'Date', 'Customer', 'NIN', 'Phone', 'Outlet', 'Agent', 'Payment', 'Total', 'Paid', 'Balance', 'Status'])
    for s in sales:
        writer.writerow([
            s.sale_ref, s.sale_date.strftime('%Y-%m-%d %H:%M'),
            s.customer.full_name, s.customer.nin, s.customer.phone_number,
            s.outlet.name, s.agent.get_full_name() if s.agent else '',
            s.get_payment_method_display(), s.total_amount,
            s.amount_paid, s.balance, s.get_status_display()
        ])
    return response
