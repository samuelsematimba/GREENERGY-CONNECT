from accounts.decorators import can_submit_collection, outlet_recon_access, backoffice_or_above, accountant_only, get_profile
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from .models import AgentCollection, OutletReconciliation, BackOfficeReconciliation
from accounts.models import Location
from sales.models import Sale
from django.db.models import Sum


@login_required
def recon_dashboard(request):
    profile = getattr(request.user, 'userprofile', None)
    context = {}
    if profile:
        role = profile.role.name if profile.role else ''
        if role in ('sales_agent',):
            context['agent_collections'] = AgentCollection.objects.filter(agent=request.user).order_by('-submitted_at')[:10]
        if role in ('outlet_manager', 'backoffice_officer', 'super_admin', 'country_admin'):
            context['outlet_recons'] = OutletReconciliation.objects.all().order_by('-created_at')[:10]
        if role in ('accountant', 'super_admin', 'country_admin'):
            context['bo_recons'] = BackOfficeReconciliation.objects.all().order_by('-created_at')[:10]
    return render(request, 'reconciliation/dashboard.html', context)


@login_required
@can_submit_collection
def submit_agent_collection(request):
    profile = getattr(request.user, 'userprofile', None)
    outlet = profile.location if profile and profile.location else None

    if request.method == 'POST':
        outlet_id = request.POST.get('outlet') or (outlet.id if outlet else None)
        period_start = request.POST.get('period_start')
        period_end = request.POST.get('period_end')
        cash = request.POST.get('cash_amount', 0) or 0
        mobile = request.POST.get('mobile_money_amount', 0) or 0
        mobile_ref = request.POST.get('mobile_money_reference', '')

        outlet_obj = get_object_or_404(Location, id=outlet_id)

        # Find all sales made by this agent at this outlet in the period
        sales_in_period = Sale.objects.filter(
            outlet=outlet_obj,
            agent=request.user,
            sale_date__date__gte=period_start,
            sale_date__date__lte=period_end
        )
        expected = sales_in_period.aggregate(
            total=Sum('amount_paid')  # use amount_paid (what was actually collected)
        )['total'] or 0

        col = AgentCollection.objects.create(
            agent=request.user, outlet=outlet_obj,
            period_start=period_start, period_end=period_end,
            cash_amount=float(cash), mobile_money_amount=float(mobile),
            mobile_money_reference=mobile_ref,
            system_expected=expected,
            status='submitted'
        )
        messages.success(request, f'Collection {col.ref} submitted. System expected: {expected} from {sales_in_period.count()} sale(s).')
        return redirect('reconciliation:agent_collection_list')

    # Preview sales for the agent to help them fill the form correctly
    recent_sales = Sale.objects.filter(
        agent=request.user
    ).order_by('-sale_date')[:10] if outlet else []

    # Total by outlet for quick reference
    outlet_sales_summary = None
    if outlet:
        outlet_sales_summary = Sale.objects.filter(
            agent=request.user, outlet=outlet
        ).aggregate(
            total_amount=Sum('total_amount'),
            total_paid=Sum('amount_paid'),
            count=Sum('total_amount') / Sum('total_amount')
        )

    context = {
        'outlet': outlet,
        'outlets': Location.objects.filter(location_type='outlet'),
        'recent_sales': recent_sales,
        'total_sales_count': Sale.objects.filter(agent=request.user, outlet=outlet).count() if outlet else 0,
        'total_sales_amount': Sale.objects.filter(agent=request.user, outlet=outlet).aggregate(t=Sum('amount_paid'))['t'] or 0,
    }
    return render(request, 'reconciliation/submit_collection.html', context)


@login_required
@can_submit_collection
def agent_collection_list(request):
    profile = getattr(request.user, 'userprofile', None)
    role = profile.role.name if (profile and profile.role) else ''
    if role == 'sales_agent':
        collections = AgentCollection.objects.filter(agent=request.user)
    elif profile and profile.location:
        collections = AgentCollection.objects.filter(outlet=profile.location)
    else:
        collections = AgentCollection.objects.all()
    return render(request, 'reconciliation/agent_collection_list.html', {'collections': collections.order_by('-submitted_at')})


@login_required
@outlet_recon_access
def review_agent_collection(request, pk):
    col = get_object_or_404(AgentCollection, pk=pk)
    if request.method == 'POST':
        action = request.POST.get('action')
        col.reviewed_by = request.user
        if action == 'balanced':
            col.status = 'balanced'
        elif action == 'discrepancy':
            col.status = 'discrepancy'
            col.discrepancy_reason = request.POST.get('discrepancy_reason', '')
        col.save()
        messages.success(request, f'Collection {col.ref} updated to {col.get_status_display()}.')
        return redirect('reconciliation:agent_collection_list')
    return render(request, 'reconciliation/review_collection.html', {'col': col})


@login_required
@outlet_recon_access
def outlet_recon_list(request):
    recons = OutletReconciliation.objects.select_related('outlet', 'outlet_manager').order_by('-created_at')
    return render(request, 'reconciliation/outlet_recon_list.html', {'recons': recons})


@login_required
@outlet_recon_access
def create_outlet_recon(request):
    profile = getattr(request.user, 'userprofile', None)
    outlet = profile.location if (profile and profile.location and profile.location.location_type == 'outlet') else None

    if request.method == 'POST':
        outlet_id = request.POST.get('outlet') or (outlet.id if outlet else None)
        period_start = request.POST.get('period_start')
        period_end = request.POST.get('period_end')
        bank_ref = request.POST.get('bank_deposit_ref', '')
        outlet_obj = get_object_or_404(Location, id=outlet_id)

        total_sales = Sale.objects.filter(
            outlet=outlet_obj, sale_date__date__gte=period_start,
            sale_date__date__lte=period_end
        ).aggregate(total=Sum('total_amount'))['total'] or 0

        total_collected = AgentCollection.objects.filter(
            outlet=outlet_obj, period_start__gte=period_start, period_end__lte=period_end, status='balanced'
        ).aggregate(
            cash=Sum('cash_amount'), mobile=Sum('mobile_money_amount')
        )
        collected = (total_collected['cash'] or 0) + (total_collected['mobile'] or 0)

        collection_ids = request.POST.getlist('collection_ids')
        recon = OutletReconciliation.objects.create(
            outlet=outlet_obj, outlet_manager=request.user,
            period_start=period_start, period_end=period_end,
            total_sales_system=total_sales, total_collected=collected,
            bank_deposit_ref=bank_ref, status='submitted'
        )
        if collection_ids:
            recon.agent_collections.set(AgentCollection.objects.filter(id__in=collection_ids))
        messages.success(request, f'Outlet reconciliation {recon.ref} submitted.')
        return redirect('reconciliation:outlet_recon_list')

    context = {
        'outlet': outlet,
        'outlets': Location.objects.filter(location_type='outlet'),
        'pending_collections': AgentCollection.objects.filter(
            outlet=outlet, status='balanced'
        ) if outlet else AgentCollection.objects.filter(status='balanced'),
    }
    return render(request, 'reconciliation/create_outlet_recon.html', context)


@login_required
@outlet_recon_access
def review_outlet_recon(request, pk):
    recon = get_object_or_404(OutletReconciliation, pk=pk)
    if request.method == 'POST':
        action = request.POST.get('action')
        recon.backoffice_officer = request.user
        if action == 'close':
            recon.status = 'closed'
            recon.closed_at = timezone.now()
        elif action == 'discrepancy':
            recon.status = 'discrepancy'
            recon.discrepancy_notes = request.POST.get('discrepancy_notes', '')
        recon.save()
        messages.success(request, f'Outlet reconciliation {recon.ref} updated.')
        return redirect('reconciliation:outlet_recon_list')
    return render(request, 'reconciliation/review_outlet_recon.html', {'recon': recon})


@login_required
@backoffice_or_above
def bo_recon_list(request):
    recons = BackOfficeReconciliation.objects.select_related('backoffice_officer', 'accountant').order_by('-created_at')
    return render(request, 'reconciliation/bo_recon_list.html', {'recons': recons})


@login_required
@backoffice_or_above
def create_bo_recon(request):
    if request.method == 'POST':
        period_start = request.POST.get('period_start')
        period_end = request.POST.get('period_end')
        bank_confirmed = request.POST.get('bank_confirmed_amount', 0)
        outlet_recon_ids = request.POST.getlist('outlet_recon_ids')

        total_outlets = OutletReconciliation.objects.filter(id__in=outlet_recon_ids).aggregate(total=Sum('total_collected'))['total'] or 0

        recon = BackOfficeReconciliation.objects.create(
            backoffice_officer=request.user,
            period_start=period_start, period_end=period_end,
            total_from_outlets=total_outlets,
            bank_confirmed_amount=float(bank_confirmed),
            status='submitted'
        )
        recon.outlet_reconciliations.set(OutletReconciliation.objects.filter(id__in=outlet_recon_ids))
        messages.success(request, f'Back-Office reconciliation {recon.ref} submitted to Accounts.')
        return redirect('reconciliation:bo_recon_list')

    closed_outlet_recons = OutletReconciliation.objects.filter(status='closed')
    return render(request, 'reconciliation/create_bo_recon.html', {'outlet_recons': closed_outlet_recons})


@login_required
@accountant_only
def signoff_bo_recon(request, pk):
    recon = get_object_or_404(BackOfficeReconciliation, pk=pk)
    if request.method == 'POST':
        recon.accountant = request.user
        recon.status = 'signed_off'
        recon.signed_off_at = timezone.now()
        recon.notes = request.POST.get('notes', '')
        recon.save()
        messages.success(request, f'Reconciliation {recon.ref} signed off. Period is now closed.')
        return redirect('reconciliation:bo_recon_list')
    return render(request, 'reconciliation/signoff_bo_recon.html', {'recon': recon})
