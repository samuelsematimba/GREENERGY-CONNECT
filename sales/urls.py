from django.urls import path
from . import views
app_name = 'sales'
urlpatterns = [
    path('', views.sale_list, name='sale_list'),
    path('create/', views.create_sale, name='create_sale'),
    path('<int:pk>/', views.sale_detail, name='sale_detail'),
    path('customers/', views.customer_list, name='customer_list'),
    path('scan/', views.scan_qr_sale, name='scan_qr'),
    path('export/', views.export_sales_csv, name='export_csv'),
]
