from django.urls import path
from .views import assessee_dashboard


urlpatterns = [
    path('dashboard/', assessee_dashboard, name='assessee_dashboard'),
]