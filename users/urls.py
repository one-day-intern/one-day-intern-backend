from django.urls import path
from .views import serve_register_company


urlpatterns = [
    path('register-company/', serve_register_company),
]
