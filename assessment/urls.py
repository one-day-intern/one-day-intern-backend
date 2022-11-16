from django.urls import path
from .views import (
    serve_get_assessment_tool,
    serve_create_assignment,
    serve_create_test_flow,
    serve_create_assessment_event,
    serve_create_response_test,
    serve_get_all_active_assignment,
    serve_create_interactive_quiz,
    serve_add_assessment_event_participant,
    serve_get_test_flow,
    serve_subscribe_to_assessment_flow,
    serve_get_assessment_event_data,
    serve_submit_assignment,
    serve_get_submitted_assignment
)

urlpatterns = [
    path('tools/', serve_get_assessment_tool),
    path('create/assignment/', serve_create_assignment),
    path('create/response-test/', serve_create_response_test, name='create-response-test'),
    path('create/interactive-quiz/', serve_create_interactive_quiz),
    path('test-flow/create/', serve_create_test_flow, name='test-flow-create'),
    path('test-flow/all/', serve_get_test_flow, name='test-flow-get'),
    path('assessment-event/create/', serve_create_assessment_event, name='assessment-event-create'),
    path('assessment-event/add-participant/', serve_add_assessment_event_participant, name='event-add-participation'),
    path('assessment-event/subscribe/', serve_subscribe_to_assessment_flow, name='event-subscription'),
    path('assessment-event/released-assignments/', serve_get_all_active_assignment, name='event-active-assignments'),
    path('assessment-event/get-data/', serve_get_assessment_event_data, name='get-event-data'),
    path('assessment-event/submit-assignments/', serve_submit_assignment, name='submit-assignments'),
    path('assessment-event/get-submitted-assignment/', serve_get_submitted_assignment, name='get-submitted-assignment'),
]
