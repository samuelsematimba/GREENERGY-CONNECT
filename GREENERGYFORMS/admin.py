import profile
from django.contrib import admin

# Register your models here.
from .models import Outlet_type, Profile
from.models import Entry
from.models import Qrcodes
from.models import Qrcodes_double
from django.contrib import admin
from.models import EmpowerCustomer,EmpowerSale,EmpowerClaim

admin.site.register(EmpowerCustomer)
admin.site.register(EmpowerClaim)
admin.site.register(EmpowerSale)

admin.site.register(Outlet_type)
admin.site.register(Entry)
admin.site.register(Qrcodes)
admin.site.register(Qrcodes_double)
admin.site.register(Profile)
