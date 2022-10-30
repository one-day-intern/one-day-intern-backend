from django.urls import path
from .views import (
    serve_get_assessment_tool,
    serve_create_assignment,
    serve_create_test_flow,
    serve_create_assessment_event,
    serve_add_assessment_event_participant,
    serve_create_response_test,
    serve_create_interactive_quiz,
    serve_add_assessment_event_participant,
    serve_subscribe_to_assessment_flow
)

urlpatterns = [
    path('tools/', serve_get_assessment_tool),
    path('create/assignment/', serve_create_assignment),
    path('create/response-test/', serve_create_response_test, name='create-response-test'),
    path('create/interactive-quiz/', serve_create_interactive_quiz),
    path('test-flow/create/', serve_create_test_flow, name='test-flow-create'),
    path('assessment-event/create/', serve_create_assessment_event, name='assessment-event-create'),
    path('assessment-event/add-participant/', serve_add_assessment_event_participant, name='event-add-participation'),
    path('assessment-event/subscribe/', serve_subscribe_to_assessment_flow, name='event-subscription'),
]
