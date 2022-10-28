from django.urls import path
from .views import serve_create_assignment, serve_create_test_flow, serve_create_assessment_event


urlpatterns = [
    path('create/assignment/', serve_create_assignment),
    path('test-flow/create/', serve_create_test_flow, name='test-flow-create'),
    path('assessment-event/create/', serve_create_assessment_event, name='assessment-event-create'),
]
