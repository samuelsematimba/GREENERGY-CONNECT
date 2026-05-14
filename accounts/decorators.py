from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages


def get_profile(user):
    return getattr(user, 'userprofile', None)


def role_required(*roles):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            profile = get_profile(request.user)
            if not profile or not profile.has_role(*roles):
                messages.error(request, "You do not have permission to access that page.")
                return redirect('accounts:dashboard')
            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator


# ── Shorthand decorators ──────────────────────────────────────────────────────

def admin_only(view_func):
    """Super Admin and Country Admin only."""
    return role_required('super_admin', 'country_admin')(view_func)


def warehouse_or_above(view_func):
    """Warehouse Manager, Country Admin, Super Admin."""
    return role_required('super_admin', 'country_admin', 'warehouse_manager')(view_func)


def outlet_or_above(view_func):
    """Outlet Manager, Warehouse Manager, Country Admin, Super Admin."""
    return role_required(
        'super_admin', 'country_admin', 'warehouse_manager', 'outlet_manager'
    )(view_func)


def sales_or_above(view_func):
    """Sales Agent, Outlet Manager, Country Admin, Super Admin."""
    return role_required(
        'super_admin', 'country_admin', 'outlet_manager', 'sales_agent'
    )(view_func)


def can_submit_collection(view_func):
    """Sales Agent and Outlet Manager can submit collections."""
    return role_required(
        'super_admin', 'country_admin', 'outlet_manager', 'sales_agent'
    )(view_func)


def outlet_recon_access(view_func):
    """Outlet Manager and Back Office Officer and above."""
    return role_required(
        'super_admin', 'country_admin', 'outlet_manager', 'backoffice_officer'
    )(view_func)


def backoffice_or_above(view_func):
    """Back-Office Officer, Accountant, Country Admin, Super Admin."""
    return role_required(
        'super_admin', 'country_admin', 'backoffice_officer', 'accountant'
    )(view_func)


def accountant_only(view_func):
    """Accountant and Super Admin only."""
    return role_required('super_admin', 'accountant')(view_func)


def reports_access(view_func):
    """Everyone except Sales Agents can see reports."""
    return role_required(
        'super_admin', 'country_admin', 'warehouse_manager',
        'outlet_manager', 'backoffice_officer', 'accountant', 'auditor'
    )(view_func)


def same_country_location(request, location):
    """
    Returns True if the user is allowed to see/touch this location.
    Super Admin sees everything. Country Admin sees own country.
    Everyone else sees only their own location.
    """
    profile = get_profile(request.user)
    if not profile:
        return False
    if profile.has_role('super_admin'):
        return True
    if profile.has_role('country_admin'):
        return profile.country == location.country
    return profile.location == location
