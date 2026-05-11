from django.contrib import admin
from .models import AgentCollection, OutletReconciliation, BackOfficeReconciliation
admin.site.register(AgentCollection)
admin.site.register(OutletReconciliation)
admin.site.register(BackOfficeReconciliation)
