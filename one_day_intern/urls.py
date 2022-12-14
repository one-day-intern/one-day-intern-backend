from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('main/', include('main.urls')),
    path('users/', include('users.urls')),
    path('assessee/', include('assessee.urls')),
    path('assessor/', include('assessor.urls')),
    path('assessment/', include('assessment.urls')),
    path('company/', include('company.urls')),
    path('video-conference/', include('video_conference.urls'))
]
