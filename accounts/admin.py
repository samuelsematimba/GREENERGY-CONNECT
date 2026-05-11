from django.contrib import admin
from .models import Country, Location, Role, UserProfile, AuditLog
admin.site.register(Country)
admin.site.register(Location)
admin.site.register(Role)
admin.site.register(UserProfile)
admin.site.register(AuditLog)
