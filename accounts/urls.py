from django.urls import path
from . import views
app_name = 'accounts'
urlpatterns = [
    path('', views.loginx, name='loginx'),
    path('login/', views.loginx, name='login'),
    path('logout/', views.logoutx, name='logoutx'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('users/', views.user_list, name='user_list'),
    path('users/create/', views.create_user, name='create_user'),
    path('users/<int:pk>/edit/', views.edit_user, name='edit_user'),
    path('users/<int:pk>/reset-password/', views.reset_user_password, name='reset_user_password'),
    path('change-password/', views.change_password, name='change_password'),
    path('locations/', views.locations_view, name='locations'),
    path('locations/create/', views.create_location, name='create_location'),
]
