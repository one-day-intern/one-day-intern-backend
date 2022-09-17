from django.urls import path
from .views import test_end_point


urlpatterns = [
    path('test/', test_end_point),
]
