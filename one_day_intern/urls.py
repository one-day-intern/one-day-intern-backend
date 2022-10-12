from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('main/', include('main.urls')),
    path('users/', include('users.urls')),
    path('assessment/', include('assessment.urls')),
]
