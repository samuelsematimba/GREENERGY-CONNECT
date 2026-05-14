"""
URL configuration for GREENERGY project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings 
from django.conf.urls.static import static

urlpatterns = [
    #path('',include('users.urls')),
    path('app', include('GREENERGYFORMS.urls')),
    path('admin/', admin.site.urls),
    path('', include('accounts.urls', namespace='accounts')),
    path('products/', include('products.urls', namespace='products')),
    path('stock/', include('stock.urls', namespace='stock')),
    path('sales/', include('sales.urls', namespace='sales')),
    path('reconciliation/', include('reconciliation.urls', namespace='reconciliation')),
    path('reports/', include('reports.urls', namespace='reports')),
    #path('forms/', include('GREENERGYFORMS.urls', namespace='GREENERGYFORMS')),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
