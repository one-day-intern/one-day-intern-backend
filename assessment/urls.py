from django.urls import path
from .views import serve_create_assignment, serve_create_test_flow


urlpatterns = [
    path('create/assignment/', serve_create_assignment),
    path('test-flow/create/', serve_create_test_flow, name='test-flow-create'),
]
