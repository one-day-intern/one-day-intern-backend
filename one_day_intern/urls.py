from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('main/', include('main.urls')),
    path('users/', include('users.urls')),
    path('assessee/', include('assessee.urls')),
    path('assessment/', include('assessment.urls')),
    path('company/', include('company.urls')),
]
