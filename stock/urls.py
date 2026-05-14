from django.urls import path
from . import views
app_name = 'stock'
urlpatterns = [
    path('', views.stock_dashboard, name='dashboard'),
    path('levels/', views.stock_levels_detail, name='stock_levels'),
    path('grn/', views.goods_receipt_list, name='grn_list'),
    path('grn/create/', views.create_goods_receipt, name='create_grn'),
    path('requests/', views.request_list, name='request_list'),
    path('requests/create/', views.create_stock_request, name='create_request'),
    path('requests/<int:pk>/review/', views.review_request, name='review_request'),
    path('requests/<int:req_pk>/dispatch/', views.dispatch_transfer, name='dispatch_transfer'),
    path('transfers/<int:transfer_pk>/confirm/', views.confirm_receipt, name='confirm_receipt'),
]
