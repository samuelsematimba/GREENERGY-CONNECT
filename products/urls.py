from django.urls import path
from . import views
app_name = 'products'
urlpatterns = [
    path('', views.product_list, name='product_list'),
    path('create/', views.create_product, name='create_product'),
    path('<int:pk>/', views.product_detail, name='product_detail'),
    path('<int:pk>/edit/', views.edit_product, name='edit_product'),
    path('<int:pk>/add-items/', views.add_serialized_items, name='add_serialized'),
    path('item/<int:item_pk>/generate-qr/', views.generate_qr_for_item, name='generate_qr'),
    path('combos/', views.combo_list, name='combo_list'),
    path('combos/create/', views.create_combo, name='create_combo'),
    # Subsidies
    path('subsidies/', views.subsidy_list, name='subsidy_list'),
    path('subsidies/create/', views.create_subsidy, name='create_subsidy'),
    path('subsidies/<int:pk>/edit/', views.edit_subsidy, name='edit_subsidy'),
    path('subsidies/ajax/for-outlet/', views.get_subsidies_for_outlet, name='subsidies_for_outlet'),
]
