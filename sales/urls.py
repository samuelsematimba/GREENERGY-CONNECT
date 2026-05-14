from django.urls import path
from . import views
app_name = 'sales'
urlpatterns = [
    path('', views.sale_list, name='sale_list'),
    path('create/', views.create_sale, name='create_sale'),
    path('<int:pk>/', views.sale_detail, name='sale_detail'),
    path('customers/', views.customer_list, name='customer_list'),
    path('customers/create/', views.create_customer, name='create_customer'),
    path('customers/<int:pk>/', views.customer_detail, name='customer_detail'),
    path('customers/bulk-upload/', views.bulk_upload_customers, name='bulk_upload_customers'),
    path('customers/template/', views.download_customer_template, name='customer_template'),
    path('scan/', views.scan_qr_sale, name='scan_qr'),
    path('export/', views.export_sales_csv, name='export_csv'),
    path('ajax/customer-search/', views.customer_search_ajax, name='customer_search_ajax'),
]
