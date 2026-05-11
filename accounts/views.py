from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.db.models import Q
from .models import UserProfile, Role, Country, Location, AuditLog


def log_action(request, action, model_name='', object_id='', previous_state=''):
    ip = request.META.get('REMOTE_ADDR')
    AuditLog.objects.create(
        user=request.user if request.user.is_authenticated else None,
        action=action, model_name=model_name,
        object_id=str(object_id), previous_state=previous_state,
        ip_address=ip
    )


def loginx(request):
    if request.user.is_authenticated:
        return redirect('accounts:dashboard')
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            profile = getattr(user, 'userprofile', None)
            if profile and profile.must_change_password:
                messages.warning(request, 'Please change your password before continuing.')
                return redirect('accounts:change_password')
            log_action(request, f'User logged in: {user.username}')
            return redirect('accounts:dashboard')
        messages.error(request, 'Invalid username or password.')
    return render(request, 'accounts/login.html')


@login_required
def logoutx(request):
    log_action(request, f'User logged out: {request.user.username}')
    logout(request)
    return redirect('accounts:loginx')


@login_required
def dashboard(request):
    profile = getattr(request.user, 'userprofile', None)
    context = {'profile': profile}
    return render(request, 'accounts/dashboard.html', context)


@login_required
def user_list(request):
    profile = getattr(request.user, 'userprofile', None)
    users = UserProfile.objects.select_related('user', 'role', 'country', 'location')
    if profile and not profile.has_role('super_admin'):
        if profile.country:
            users = users.filter(country=profile.country)

    q = request.GET.get('q', '')
    country_id = request.GET.get('country', '')
    role_id = request.GET.get('role', '')
    if q:
        users = users.filter(Q(user__first_name__icontains=q) | Q(user__last_name__icontains=q) | Q(user__username__icontains=q))
    if country_id:
        users = users.filter(country_id=country_id)
    if role_id:
        users = users.filter(role_id=role_id)

    context = {
        'users': users.order_by('user__first_name'),
        'countries': Country.objects.all(),
        'roles': Role.objects.all(),
        'q': q, 'country_id': country_id, 'role_id': role_id,
    }
    return render(request, 'accounts/user_list.html', context)


@login_required
def create_user(request):
    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone_number', '').strip()
        role_id = request.POST.get('role')
        country_id = request.POST.get('country')
        location_id = request.POST.get('location')
        password = request.POST.get('password', '')

        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already taken.')
        else:
            user = User.objects.create_user(
                username=username, email=email,
                password=password, first_name=first_name, last_name=last_name
            )
            UserProfile.objects.create(
                user=user,
                role=Role.objects.get(id=role_id) if role_id else None,
                country=Country.objects.get(id=country_id) if country_id else None,
                location=Location.objects.get(id=location_id) if location_id else None,
                phone_number=phone,
                created_by=request.user,
                must_change_password=True,
            )
            log_action(request, f'Created user: {username}', 'User', user.id)
            messages.success(request, f'User {first_name} {last_name} created successfully.')
            return redirect('accounts:user_list')

    context = {
        'roles': Role.objects.all(),
        'countries': Country.objects.all(),
        'locations': Location.objects.all(),
    }
    return render(request, 'accounts/create_user.html', context)


@login_required
def edit_user(request, pk):
    profile = get_object_or_404(UserProfile, pk=pk)
    if request.method == 'POST':
        profile.user.first_name = request.POST.get('first_name', profile.user.first_name)
        profile.user.last_name = request.POST.get('last_name', profile.user.last_name)
        profile.user.email = request.POST.get('email', profile.user.email)
        profile.user.save()
        role_id = request.POST.get('role')
        country_id = request.POST.get('country')
        location_id = request.POST.get('location')
        profile.phone_number = request.POST.get('phone_number', profile.phone_number)
        profile.role = Role.objects.get(id=role_id) if role_id else profile.role
        profile.country = Country.objects.get(id=country_id) if country_id else profile.country
        profile.location = Location.objects.get(id=location_id) if location_id else profile.location
        profile.is_active = 'is_active' in request.POST
        profile.save()
        log_action(request, f'Updated user: {profile.user.username}', 'UserProfile', pk)
        messages.success(request, 'User updated successfully.')
        return redirect('accounts:user_list')

    context = {
        'profile': profile,
        'roles': Role.objects.all(),
        'countries': Country.objects.all(),
        'locations': Location.objects.all(),
    }
    return render(request, 'accounts/edit_user.html', context)


@login_required
def change_password(request):
    if request.method == 'POST':
        current = request.POST.get('current_password', '')
        new_pass = request.POST.get('new_password', '')
        confirm = request.POST.get('confirm_password', '')
        if not request.user.check_password(current):
            messages.error(request, 'Current password is incorrect.')
        elif new_pass != confirm:
            messages.error(request, 'New passwords do not match.')
        elif len(new_pass) < 8:
            messages.error(request, 'Password must be at least 8 characters.')
        else:
            request.user.set_password(new_pass)
            request.user.save()
            profile = getattr(request.user, 'userprofile', None)
            if profile:
                profile.must_change_password = False
                profile.save()
            update_session_auth_hash(request, request.user)
            log_action(request, f'Password changed: {request.user.username}')
            messages.success(request, 'Password changed successfully.')
            return redirect('accounts:dashboard')
    return render(request, 'accounts/change_password.html')


@login_required
def reset_user_password(request, pk):
    profile = get_object_or_404(UserProfile, pk=pk)
    if request.method == 'POST':
        new_pass = request.POST.get('new_password', '')
        profile.user.set_password(new_pass)
        profile.user.save()
        profile.must_change_password = True
        profile.save()
        log_action(request, f'Admin reset password for: {profile.user.username}', 'User', profile.user.id)
        messages.success(request, f'Password reset for {profile.full_name}.')
        return redirect('accounts:user_list')
    return render(request, 'accounts/reset_password.html', {'profile': profile})


@login_required
def locations_view(request):
    locations = Location.objects.select_related('country', 'affiliated_warehouse')
    context = {'locations': locations, 'countries': Country.objects.all()}
    return render(request, 'accounts/locations.html', context)


@login_required
def create_location(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        location_type = request.POST.get('location_type')
        country_id = request.POST.get('country')
        address = request.POST.get('address', '')
        warehouse_id = request.POST.get('affiliated_warehouse')
        country = get_object_or_404(Country, id=country_id)
        warehouse = Location.objects.filter(id=warehouse_id).first() if warehouse_id else None
        loc = Location.objects.create(
            name=name, location_type=location_type, country=country,
            address=address, affiliated_warehouse=warehouse
        )
        log_action(request, f'Created location: {name}', 'Location', loc.id)
        messages.success(request, f'Location "{name}" created.')
        return redirect('accounts:locations')
    context = {
        'countries': Country.objects.all(),
        'warehouses': Location.objects.filter(location_type='warehouse'),
    }
    return render(request, 'accounts/create_location.html', context)
