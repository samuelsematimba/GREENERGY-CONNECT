from django.urls import path, include
from .import views
from django.conf.urls.static import static
from django.conf import settings

app_name ='GREENERGYFORMS'
urlpatterns=[
    path('index',views.index,name='index'),
    path('GREENERGY_CUSTOMER_FORMS/',views.GREENERGY_CUSTOMER_FORMS,name='GREENERGY_CUSTOMER_FORMS'),
    path('save/',views.save,name='save'),
    path('view_data/',views.view_data,name='view_data'),
    path('qr_codes/',views.qr_codes,name='qr_codes'),
    path('save2/',views.save2,name='save2'),
    path('makeqr/',views.makeqr,name='makeqr'),
    path('show_qr/',views.show_qr,name='show_qr'),
    path('save3/',views.save3,name='save3'),
    path('empower/',views.empower,name='empower'),
    path('empower_register/', views.empower_register, name='empower_register'),
    path('empower_claim/', views.empower_claim, name='empower_claim'),
    path('empower_records/', views.empower_records, name='empower_records'),
    path('download_template/', views.download_template, name='download_template'),
    path('upload_csv/', views.upload_csv, name='upload_csv'),
    path('upload/', views.upload, name='upload'),
    path('empower_verify/', views.empower_verify, name='empower_verify'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL,document_root=settings.MEDIA_ROOT)