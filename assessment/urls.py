from django.urls import path
from .views import serve_create_assignment


urlpatterns = [
    path('create/assignment/', serve_create_assignment),
]
