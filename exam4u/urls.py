from django.contrib import admin
from django.urls import path, include
from app import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('app.urls')),
]

handler403 = 'app.views.custom_403'
handler404 = 'app.views.custom_404'