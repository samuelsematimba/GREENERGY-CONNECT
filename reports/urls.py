from django.urls import path
from . import views
app_name = 'reports'
urlpatterns = [
    path('', views.reports_home, name='home'),
    path('users/', views.user_report, name='user_report'),
    path('products/', views.product_report, name='product_report'),
    path('stock/', views.stock_report, name='stock_report'),
    path('sales/', views.sales_report, name='sales_report'),
    path('reconciliation/', views.reconciliation_report, name='reconciliation_report'),
    path('audit/', views.audit_log_report, name='audit_log'),
    path('export/<str:report_type>/', views.export_report_csv, name='export_csv'),
]
