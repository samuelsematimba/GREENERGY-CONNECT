from django.urls import path
from . import views
app_name = 'reconciliation'
urlpatterns = [
    path('', views.recon_dashboard, name='dashboard'),
    path('collections/', views.agent_collection_list, name='agent_collection_list'),
    path('collections/submit/', views.submit_agent_collection, name='submit_collection'),
    path('collections/<int:pk>/review/', views.review_agent_collection, name='review_collection'),
    path('outlet/', views.outlet_recon_list, name='outlet_recon_list'),
    path('outlet/create/', views.create_outlet_recon, name='create_outlet_recon'),
    path('outlet/<int:pk>/review/', views.review_outlet_recon, name='review_outlet_recon'),
    path('backoffice/', views.bo_recon_list, name='bo_recon_list'),
    path('backoffice/create/', views.create_bo_recon, name='create_bo_recon'),
    path('backoffice/<int:pk>/signoff/', views.signoff_bo_recon, name='signoff_bo_recon'),
]
