from django.urls import path
from .views import (
    serve_get_assessment_tool,
    serve_create_assignment,
    serve_create_test_flow,
    serve_create_assessment_event,
    serve_update_assessment_event,
    serve_delete_assessment_event,
    serve_create_response_test,
    serve_get_all_active_assignment,
    serve_create_interactive_quiz,
    serve_add_assessment_event_participant,
    serve_get_test_flow,
    serve_subscribe_to_assessment_flow,
    serve_get_assessment_event_data,
    serve_submit_assignment,
    serve_get_submitted_assignment,
    serve_submit_interactive_quiz,
    serve_submit_answer,
    serve_get_assessee_progress_on_event,
    serve_grade_assessment_tool_attempts,
    serve_get_assignment_attempt_data,
    serve_get_assignment_attempt_file,
    serve_grade_individual_question_attempts,
    serve_save_graded_attempt,
    serve_get_interactive_quiz_attempt_data
)

urlpatterns = [
    path('tools/', serve_get_assessment_tool),
    path('create/assignment/', serve_create_assignment),
    path('create/response-test/', serve_create_response_test, name='create-response-test'),
    path('create/interactive-quiz/', serve_create_interactive_quiz),
    path('test-flow/create/', serve_create_test_flow, name='test-flow-create'),
    path('test-flow/all/', serve_get_test_flow, name='test-flow-get'),
    path('assessment-event/create/', serve_create_assessment_event, name='assessment-event-create'),
    path('assessment-event/update/', serve_update_assessment_event, name='assessment-event-update'),
    path('assessment-event/delete/', serve_delete_assessment_event, name='assessment-event-delete'),
    path('assessment-event/add-participant/', serve_add_assessment_event_participant, name='event-add-participation'),
    path('assessment-event/subscribe/', serve_subscribe_to_assessment_flow, name='event-subscription'),
    path('assessment-event/released-assignments/', serve_get_all_active_assignment, name='event-active-assignments'),
    path('assessment-event/get-data/', serve_get_assessment_event_data, name='get-event-data'),
    path('assessment-event/submit-assignments/', serve_submit_assignment, name='submit-assignments'),
    path('assessment-event/get-submitted-assignment/', serve_get_submitted_assignment, name='get-submitted-assignment'),
    path('assessment-event/submit-answers/', serve_submit_answer, name='submit-interactive-quiz-answers'),
    path('assessment-event/submit-interactive_quiz/', serve_submit_interactive_quiz, name='submit-interactive-quiz'),
    path('assessment-event/progress/', serve_get_assessee_progress_on_event, name='get-assessee-progress'),
    path('grade/submit-grade-and-note/', serve_grade_assessment_tool_attempts, name='submit-grade-and-note'),
    path('grade/individual-question/', serve_grade_individual_question_attempts, name='grade-individual-question'),
    path('grade/interactive-quiz/', serve_save_graded_attempt, name='grade-interactive-quiz'),
    path('review/interactive-quiz/', serve_get_interactive_quiz_attempt_data, name='review-interactive-quiz'),
    path('review/assignment/data/', serve_get_assignment_attempt_data, name='get-assignment-attempt-data'),
    path('review/assignment/file/', serve_get_assignment_attempt_file, name='get-assignment-attempt-file'),
]