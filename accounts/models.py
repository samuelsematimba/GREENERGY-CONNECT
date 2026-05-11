from django.db import models
from django.contrib.auth.models import User


class Country(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10, unique=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Countries"


class Location(models.Model):
    LOCATION_TYPE_CHOICES = [
        ('warehouse', 'Warehouse'),
        ('outlet', 'Outlet'),
        ('office', 'Office'),
    ]
    name = models.CharField(max_length=150)
    location_type = models.CharField(max_length=20, choices=LOCATION_TYPE_CHOICES)
    country = models.ForeignKey(Country, on_delete=models.CASCADE, related_name='locations')
    address = models.TextField(blank=True)
    affiliated_warehouse = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='outlets', limit_choices_to={'location_type': 'warehouse'}
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.get_location_type_display()}) — {self.country.name}"


class Role(models.Model):
    ROLE_CHOICES = [
        ('super_admin', 'Super Admin'),
        ('country_admin', 'Country Admin'),
        ('warehouse_manager', 'Warehouse Manager'),
        ('outlet_manager', 'Outlet Manager'),
        ('sales_agent', 'Sales Agent'),
        ('backoffice_officer', 'Back-Office Officer'),
        ('accountant', 'Accountant'),
        ('auditor', 'Auditor / Viewer'),
    ]
    name = models.CharField(max_length=50, choices=ROLE_CHOICES, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.get_name_display()


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='userprofile')
    role = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True)
    country = models.ForeignKey(Country, on_delete=models.SET_NULL, null=True, blank=True)
    location = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    is_active = models.BooleanField(default=True)
    must_change_password = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_users'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username}"

    @property
    def full_name(self):
        return self.user.get_full_name() or self.user.username

    def has_role(self, *roles):
        return self.role and self.role.name in roles


class AuditLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=255)
    model_name = models.CharField(max_length=100, blank=True)
    object_id = models.CharField(max_length=50, blank=True)
    previous_state = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    def __str__(self):
        return f"{self.user} | {self.action} | {self.timestamp}"

    class Meta:
        ordering = ['-timestamp']
