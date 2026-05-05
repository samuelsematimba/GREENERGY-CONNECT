"""defines url pattern for the users"""
from django.urls import path, include
from . import views 
from django.contrib.auth import views as auth_views


app_name='users'
urlpatterns=[
    #includes the path to the default django view
    path('',views.loginx,name="loginx"),
    path('login',views.logins,name="logins"),
    path('logout/', auth_views.LogoutView.as_view(next_page='users:loginx'), name='logout'),
    path('change-password/', auth_views.PasswordChangeView.as_view(
        template_name='users/change_password.html',
        success_url='/'
    ), name='change_password'),
    path('upload-avatar/', views.upload_avatar, name='upload_avatar'),
]