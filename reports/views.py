from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Q
from django.http import HttpResponse
from accounts.models import UserProfile, AuditLog, Country, Location
from products.models import Product, SerializedItem
from stock.models import StockLevel, StockTransfer, GoodsReceipt, WriteOff, StockRequest
from sales.models import Sale, Customer
from reconciliation.models import AgentCollection, OutletReconciliation, BackOfficeReconciliation
import csv


@login_required
def reports_home(request):
    return render(request, 'reports/home.html')


@login_required
def user_report(request):
    users = UserProfile.objects.select_related('user', 'role', 'country', 'location')
    country_id = request.GET.get('country', '')
    role_id = request.GET.get('role', '')
    status = request.GET.get('status', '')
    if country_id:
        users = users.filter(country_id=country_id)
    if role_id:
        users = users.filter(role_id=role_id)
    if status == 'active':
        users = users.filter(is_active=True)
    elif status == 'inactive':
        users = users.filter(is_active=False)
    context = {
        'users': users,
        'countries': Country.objects.all(),
        'total': users.count(),
        'country_id': country_id, 'role_id': role_id, 'status': status,
    }
    return render(request, 'reports/user_report.html', context)


@login_required
def product_report(request):
    products = Product.objects.select_related('category').prefetch_related('countries')
    ptype = request.GET.get('type', '')
    country_id = request.GET.get('country', '')
    q = request.GET.get('q', '')
    if ptype:
        products = products.filter(product_type=ptype)
    if country_id:
        products = products.filter(countries__id=country_id)
    if q:
        products = products.filter(name__icontains=q)

    serialized_stats = SerializedItem.objects.values('status').annotate(count=Count('id'))
    context = {
        'products': products,
        'serialized_stats': {s['status']: s['count'] for s in serialized_stats},
        'countries': Country.objects.all(),
        'ptype': ptype, 'country_id': country_id, 'q': q,
    }
    return render(request, 'reports/product_report.html', context)


@login_required
def stock_report(request):
    profile = getattr(request.user, 'userprofile', None)
    location_id = request.GET.get('location', '')
    country_id = request.GET.get('country', '')

    stock_levels = StockLevel.objects.select_related('product', 'location__country')
    serialized = SerializedItem.objects.select_related('product', 'current_location__country')
    transfers = StockTransfer.objects.select_related('from_location', 'to_location').order_by('-dispatch_date')
    write_offs = WriteOff.objects.select_related('product', 'location').order_by('-date')

    if profile and not profile.has_role('super_admin') and profile.country:
        stock_levels = stock_levels.filter(location__country=profile.country)
        serialized = serialized.filter(current_location__country=profile.country)

    if location_id:
        stock_levels = stock_levels.filter(location_id=location_id)
        serialized = serialized.filter(current_location_id=location_id)
    if country_id:
        stock_levels = stock_levels.filter(location__country_id=country_id)
        serialized = serialized.filter(current_location__country_id=country_id)

    context = {
        'stock_levels': stock_levels,
        'serialized': serialized,
        'in_transit': transfers.filter(status__in=['dispatched', 'in_transit']),
        'write_offs': write_offs[:20],
        'locations': Location.objects.all(),
        'countries': Country.objects.all(),
        'location_id': location_id, 'country_id': country_id,
    }
    return render(request, 'reports/stock_report.html', context)


@login_required
def sales_report(request):
    profile = getattr(request.user, 'userprofile', None)
    sales = Sale.objects.select_related('customer', 'outlet', 'agent').prefetch_related('items')

    if profile and profile.location and profile.location.location_type == 'outlet':
        sales = sales.filter(outlet=profile.location)

    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    location_id = request.GET.get('location', '')
    country_id = request.GET.get('country', '')
    payment = request.GET.get('payment', '')
    q = request.GET.get('q', '')

    if date_from:
        sales = sales.filter(sale_date__date__gte=date_from)
    if date_to:
        sales = sales.filter(sale_date__date__lte=date_to)
    if location_id:
        sales = sales.filter(outlet_id=location_id)
    if country_id:
        sales = sales.filter(outlet__country_id=country_id)
    if payment:
        sales = sales.filter(payment_method=payment)
    if q:
        sales = sales.filter(Q(customer__full_name__icontains=q) | Q(sale_ref__icontains=q))

    totals = sales.aggregate(revenue=Sum('total_amount'), paid=Sum('amount_paid'), count=Count('id'))
    context = {
        'sales': sales.order_by('-sale_date'),
        'totals': totals,
        'locations': Location.objects.filter(location_type='outlet'),
        'countries': Country.objects.all(),
        'date_from': date_from, 'date_to': date_to, 'payment': payment, 'q': q,
    }
    return render(request, 'reports/sales_report.html', context)


@login_required
def reconciliation_report(request):
    agent_cols = AgentCollection.objects.select_related('agent', 'outlet').order_by('-submitted_at')
    outlet_recons = OutletReconciliation.objects.select_related('outlet', 'outlet_manager').order_by('-created_at')
    bo_recons = BackOfficeReconciliation.objects.select_related('backoffice_officer', 'accountant').order_by('-created_at')

    status_filter = request.GET.get('status', '')
    if status_filter:
        outlet_recons = outlet_recons.filter(status=status_filter)

    context = {
        'agent_cols': agent_cols[:20],
        'outlet_recons': outlet_recons,
        'bo_recons': bo_recons,
        'status_filter': status_filter,
    }
    return render(request, 'reports/reconciliation_report.html', context)


@login_required
def export_report_csv(request, report_type):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{report_type}_report.csv"'
    writer = csv.writer(response)

    if report_type == 'sales':
        sales = Sale.objects.select_related('customer', 'outlet', 'agent')
        date_from = request.GET.get('date_from', '')
        date_to = request.GET.get('date_to', '')
        if date_from: sales = sales.filter(sale_date__date__gte=date_from)
        if date_to: sales = sales.filter(sale_date__date__lte=date_to)
        writer.writerow(['Sale Ref', 'Date', 'Customer', 'NIN', 'Phone', 'Outlet', 'Agent', 'Payment', 'Total', 'Paid', 'Status'])
        for s in sales:
            writer.writerow([s.sale_ref, s.sale_date.strftime('%Y-%m-%d'), s.customer.full_name, s.customer.nin,
                             s.customer.phone_number, s.outlet.name,
                             s.agent.get_full_name() if s.agent else '', s.payment_method,
                             s.total_amount, s.amount_paid, s.status])

    elif report_type == 'stock':
        writer.writerow(['Product', 'SKU', 'Location', 'Country', 'Quantity'])
        for sl in StockLevel.objects.select_related('product', 'location__country'):
            writer.writerow([sl.product.name, sl.product.sku, sl.location.name, sl.location.country.name, sl.quantity])

    elif report_type == 'users':
        writer.writerow(['Username', 'Full Name', 'Email', 'Role', 'Country', 'Location', 'Status'])
        for up in UserProfile.objects.select_related('user', 'role', 'country', 'location'):
            writer.writerow([up.user.username, up.full_name, up.user.email,
                             str(up.role), str(up.country), str(up.location),
                             'Active' if up.is_active else 'Inactive'])

    elif report_type == 'reconciliation':
        writer.writerow(['Ref', 'Outlet', 'Period Start', 'Period End', 'System Sales', 'Collected', 'Status'])
        for r in OutletReconciliation.objects.select_related('outlet'):
            writer.writerow([r.ref, r.outlet.name, r.period_start, r.period_end,
                             r.total_sales_system, r.total_collected, r.status])

    return response


@login_required
def audit_log_report(request):
    logs = AuditLog.objects.select_related('user').order_by('-timestamp')
    q = request.GET.get('q', '')
    if q:
        logs = logs.filter(Q(action__icontains=q) | Q(user__username__icontains=q))
    return render(request, 'reports/audit_log.html', {'logs': logs[:200], 'q': q})
