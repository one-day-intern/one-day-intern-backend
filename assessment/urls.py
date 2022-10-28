from django.urls import path
from .views import (
    serve_create_assignment,
    serve_create_test_flow,
    serve_create_assessment_event,
    serve_add_assessment_event_participant,
    serve_create_response_test
)


urlpatterns = [
    path('create/assignment/', serve_create_assignment),
    path('create/response-test/', serve_create_response_test, name='create-response-test'),
    path('test-flow/create/', serve_create_test_flow, name='test-flow-create'),
    path('assessment-event/create/', serve_create_assessment_event, name='assessment-event-create'),
    path('assessment-event/add-participant/', serve_add_assessment_event_participant, name='event-add-participation'),
]
