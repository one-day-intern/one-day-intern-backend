from django.urls import path
from .views import assessor_dashboard


urlpatterns = [
    path('dashboard/', assessor_dashboard, name='assessor_dashboard'),
]