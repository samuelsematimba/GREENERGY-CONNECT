def user_role(request):
    """
    Injects the current user's role name into every template context.
    Use like: {% if role == 'super_admin' %} or {% if role in admin_roles %}
    """
    role = None
    if request.user.is_authenticated:
        profile = getattr(request.user, 'userprofile', None)
        if profile and profile.role:
            role = profile.role.name
    return {'user_role': role}
