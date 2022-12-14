from django.core.exceptions import ObjectDoesNotExist
from django.views.decorators.http import require_POST, require_GET
from django.http.response import HttpResponse, StreamingHttpResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from assessment.services.assessment_tool import (
    get_assessment_tool_by_company,
    get_test_flow_by_company,
    serialize_assignment_list_using_serializer,
    serialize_test_flow_list
)
from .services.assessment import create_assignment, create_interactive_quiz, create_response_test, \
    create_video_conference_notification
from one_day_intern.exceptions import RestrictedAccessException
from users.services import utils as user_utils
from .services import utils
from .services.test_flow import create_test_flow
from .services.assessment_event import (
    create_assessment_event,
    add_assessment_event_participation,
    update_assessment_event,
    delete_assessment_event
)
from .services.assessment_event_attempt import (
    subscribe_to_assessment_flow,
    get_all_active_assignment,
    get_all_active_response_test,
    get_submitted_response_test,
    get_assessment_event_data,
    submit_response_test,
    submit_assignment,
    get_submitted_assignment,
    submit_interactive_quiz,
    submit_interactive_quiz_answers,
    get_all_active_interactive_quiz,
    get_submitted_individual_question,
    get_submitted_interactive_quiz

)
from .services.progress_review import (
    get_assessee_progress_on_assessment_event,
    get_assessee_report_on_assessment_event,
    assessor_get_assessment_event_data
)
from .services.grading import (
    grade_assessment_tool,
    get_assignment_attempt_data,
    get_assignment_attempt_file,
    get_response_test_attempt_data,
    grade_interactive_quiz_individual_question,
    grade_interactive_quiz,
    get_interactive_quiz_grading_data,
    get_question_grading_data
)
from .models import (
    AssignmentSerializer,
    TestFlowSerializer,
    AssessmentEventSerializer,
    InteractiveQuizSerializer,
    ResponseTestSerializer,
    ToolAttemptSerializer,
    AssignmentAttemptSerializer,
    VideoConferenceNotificationSerializer,
    ResponseTestAttemptSerializer,
    GradedResponseTestAttemptSerializer
)
import json

NO_ATTEMPT_FOUND = 'No attempt found'


@require_GET
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def serve_get_assessment_tool(request):
    assignments = get_assessment_tool_by_company(request.user)
    response_data = serialize_assignment_list_using_serializer(assignments)
    return Response(data=response_data)


@require_GET
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def serve_get_test_flow(request):
    test_flows = get_test_flow_by_company(request.user)
    response_data = serialize_test_flow_list(test_flows)
    return Response(data=response_data)


@require_POST
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def serve_create_assignment(request):
    """
    request_data must contain
    name (string),
    description (string),
    duration_in_minutes (integer),
    expected_file_format (string, without leading .)
    """
    request_data = json.loads(request.body.decode('utf-8'))
    assignment = create_assignment(request_data, request.user)
    response_data = AssignmentSerializer(assignment).data
    return Response(data=response_data)


@require_POST
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def serve_create_interactive_quiz(request):
    """
    request_data must contain
    name (string),
    description (string),
    duration_in_minutes (integer),
    total_points (integer)
    """
    request_data = json.loads(request.body.decode('utf-8'))
    interactive_quiz = create_interactive_quiz(request_data, request.user)
    response_data = InteractiveQuizSerializer(interactive_quiz).data
    return Response(data=response_data)


@require_POST
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def serve_create_test_flow(request):
    """
    Endpoint can only be accessed by company/assessor
    request_data must contain
    test_flow_name,
    tools_used (in the form of a list, with dictionaries as its elements)
    tools_used is OPTIONAL, when not present, a test flow with no tools will be created
    A valid request looks like this.
    {
        "name": <test flow name>,
        "tools_used": [
            {
                "tool_id": <tool-id-uuid>,
                "release_time": <release-time>,
                "start_working_time": <start-working-time>
            }
        ]
    }
    """
    request_data = json.loads(request.body.decode('utf-8'))
    test_flow = create_test_flow(request_data, user=request.user)
    response_data = TestFlowSerializer(test_flow).data
    return Response(data=response_data)


@require_POST
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def serve_create_assessment_event(request):
    """
    Endpoint can only be accessed by company/assessor,
    request_data must contain
    name,
    start_date,
    test_flow_id
    """
    request_data = json.loads(request.body.decode('utf-8'))
    assessment_event = create_assessment_event(request_data, user=request.user)
    response_data = AssessmentEventSerializer(assessment_event).data
    return Response(data=response_data)


@require_POST
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def serve_add_assessment_event_participant(request):
    """
    Endpoint can only be accessed by assessor
    request_data must contain
    assessment_event_id,
    list_of_participants,
    containing the assessee_id and assessor_id
    of the assessor assigned to the assessee
    A valid request looks like this.
    {
        assessment_event_id: <AssessmentEventId>
        list_of_participants: [
            {
                assessee_email: <AssesseeEmail>,
                assessor_email: <AssessorEmail>
            }
        ]
    }
    """
    request_data = json.loads(request.body.decode('utf-8'))
    add_assessment_event_participation(request_data, user=request.user)
    return Response(data={'message': 'Participants are successfully added'})


@require_POST
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def serve_create_response_test(request):
    """
    request_data must contain
    sender
    prompt
    subject
    """
    request_data = json.loads(request.body.decode('utf-8'))
    assignment = create_response_test(request_data, request.user)
    response_data = ResponseTestSerializer(assignment).data
    return Response(data=response_data)


@require_POST
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def serve_create_video_conference_notification(request):
    """
    request_data must contain
    sender
    prompt
    subject
    """
    request_data = json.loads(request.body.decode('utf-8'))
    assignment = create_video_conference_notification(request_data, request.user)
    response_data = VideoConferenceNotificationSerializer(assignment).data
    return Response(data=response_data)


@require_GET
def serve_subscribe_to_assessment_flow(request):
    """
        Endpoint can only be accessed by assessee
        Endpoint will return an event stream,
        returning the assessment tool data at each designated time.
        A valid request looks like this.
        /assessment-event-id=<AssessmentEventId>
        """
    try:
        request_data = request.GET
        user = user_utils.get_user_from_request(request)
        task_generator = subscribe_to_assessment_flow(request_data, user=user)
        return StreamingHttpResponse(task_generator.generate(), status=200, content_type='text/event-stream')
    except RestrictedAccessException as exception:
        response_content = {'message': str(exception)}
        return HttpResponse(content=json.dumps(response_content), status=403)
    except ObjectDoesNotExist as exception:
        response_content = {'message': str(exception)}
        return HttpResponse(content=json.dumps(response_content), status=400)
    except Exception as exception:
        response_content = {'message': str(exception)}
        return HttpResponse(content=json.dumps(response_content), status=500)


@require_GET
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def serve_get_all_active_response_test(request):
    """
    This view will serve as the end-point for assessees to get all active response tests (response tests
    that have been released) in the current assessment event that they participate in.
    ----------------------------------------------------------
    request-data must contain:
    assessment-event-id: string
    """
    request_data = request.GET
    active_response_tests = get_all_active_response_test(request_data, user=request.user)
    return Response(data=active_response_tests)


@require_POST
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def serve_submit_response_test(request):
    """
    This view will serve as the end-point for assessees to submit their response test
    attempt to an response test tool that they currently undergo in an assessment event.
    ----------------------------------------------------------
    request-data must contain:
    assessment-event-id: string
    assessment-tool-id: string
    subject: string
    response: string
    """
    request_data = json.loads(request.body.decode('utf-8'))
    submit_response_test(request_data, user=request.user)
    return Response(data={'message': 'Response test has been saved successfully'}, status=200)


@require_GET
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def serve_get_submitted_response_test(request):
    """
    This view will serve as the end-point for assessees to get the response test attempt that they
    have submitted.
    ----------------------------------------------------------
    request-param must contain:
    assessment-event-id: string
    assessment-tool-id: string
    """
    request_data = request.GET
    response_test_attempt = get_submitted_response_test(request_data, user=request.user)
    response_data = ResponseTestAttemptSerializer(response_test_attempt).data
    return Response(data=response_data, status=200)


@require_GET
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def serve_get_all_active_assignment(request):
    """
    Endpoint that can only be accessed by assessee.
    Assessee authentication-related information should be present through the JWT.
    URL structure /active-assignment/?assessment-event-id=<assessment-event-id>
    """
    request_data = request.GET
    active_assignments = get_all_active_assignment(request_data, user=request.user)
    return Response(data=active_assignments)


@require_GET
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def serve_get_assessment_event_data(request):
    """
    This view will verify whether an assessee if part of an
    assessment event. When the participation is valid, the
    view will return the assessment event data to the assessee.
    ----------------------------------------------------------
    request-param must contain:
    assessment-event-id: string
    """
    request_data = request.GET
    event = get_assessment_event_data(request_data, user=request.user)
    response_data = AssessmentEventSerializer(event).data
    return Response(data=response_data, status=200)


@require_POST
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def serve_submit_assignment(request):
    """
    This view will serve as the end-point for assessees to submit their assignment
    attempt to an assignment tool that they currently undergo in an assessment event.
    ----------------------------------------------------------
    request-data must contain:
    assessment-event-id: string
    assessment-tool-id: string
    file: file
    """
    request_data = request.POST.dict()
    submitted_file = request.FILES.get('file')
    submit_assignment(request_data, submitted_file, user=request.user)
    return Response(data={'message': 'File uploaded successfully'}, status=200)


@require_GET
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def serve_get_submitted_assignment(request):
    """
    This view will serve as the end-point for assessees to download their submitted assignment
    ----------------------------------------------------------
    request-data must contain:
    assessment-event-id: string
    assessment-tool-id: string
    Format:
    assessment/assessment-event/?assessment-event-id=<AssessmentEventId>&assignment-tool-id=<AssignmentId>
    """
    request_data = request.GET
    downloaded_file = get_submitted_assignment(request_data, user=request.user)
    if downloaded_file:
        return utils.generate_file_response(downloaded_file)
    else:
        return Response(data={'message': NO_ATTEMPT_FOUND}, status=200)


@require_GET
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def serve_get_all_active_interactive_quizzes(request):
    """
    Endpoint that can only be accessed by assessee.
    Assessee authentication-related information should be present through the JWT.
    URL structure /active-interactive-quizzes/?assessment-event-id=<assessment-event-id>
    """
    request_data = request.GET
    active_quizzes = get_all_active_interactive_quiz(request_data, user=request.user)
    return Response(data=active_quizzes)


@require_GET
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def serve_get_submitted_quiz(request):
    """
        This view will serve as the end-point for assessees to view their quiz
        ----------------------------------------------------------
        request-data must contain:
        assessment-event-id: string
        assessment-tool-id: string
        Format:
        assessment-event/get-submitted-quiz/?assessment-event-id=<EventId>&quiz-tool-id=<InteractiveQuizId>
    """
    request_data = request.GET
    quiz_data = get_submitted_interactive_quiz(request_data, user=request.user)
    if quiz_data:
        return Response(data=quiz_data, status=200)
    else:
        return Response(data={'message': NO_ATTEMPT_FOUND}, status=200)


@require_GET
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def serve_get_submitted_question(request):
    """
        This view will serve as the end-point for assessees to view their submitted quiz
        ----------------------------------------------------------
        request-data must contain:
        assessment-event-id: string
        assessment-tool-id: string
        question-attempt-id: string
        Format:
        assessment-event/get-submitted-question/?assessment-event-id=<EventId>
        &assessment-tool-id=<InteractiveQuizId>
        &question-attempt-id=<QuestionAttemptId>
    """
    request_data = request.GET
    question_data = get_submitted_individual_question(request_data, user=request.user)
    if question_data:
        return Response(data=question_data, status=200)
    else:
        return Response(data={'message': NO_ATTEMPT_FOUND}, status=200)


@require_POST
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def serve_submit_answer(request):
    """
    This view will serve as the end-point for assessees to submit their assignment
    attempt to an interactive quiz tool that they currently undergo in an assessment event.
    ----------------------------------------------------------
    request-data must contain:
    assessment-event-id: string
    assessment-tool-id: string
    question-attempt-id: string
    """
    request_data = json.loads(request.body.decode('utf-8'))
    submit_interactive_quiz_answers(request_data, user=request.user)
    return Response(data={'message': 'Answers saved successfully'}, status=200)


@require_POST
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def serve_submit_interactive_quiz(request):
    """
    This view will serve as the end-point for assessees to submit their assignment
    attempt to an interactive quiz tool that they currently undergo in an assessment event.
    ----------------------------------------------------------
    request-data must contain:
    assessment-event-id: string
    assessment-tool-id: string
    """
    request_data = json.loads(request.body.decode('utf-8'))
    submit_interactive_quiz(request_data, user=request.user)
    return Response(data={'message': 'All answers saved successfully'}, status=200)


@require_GET
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def serve_get_assessee_progress_on_event(request):
    """
    This view will serve as the end point for assessors to get assessment event progress of an assessee
    ----------------------------------------------------------
    request-param must contain:
    assessment-event-id: string
    assessee-email: string
    """
    request_data = request.GET
    progress_data = get_assessee_progress_on_assessment_event(request_data, user=request.user)
    return Response(data=progress_data)


@require_GET
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def serve_assessor_get_assessment_event_data(request):
    """
    This view will serve as the end point for assessors to get assessment event data
    ----------------------------------------------------------
    request-param must contain:
    assessment-event-id: string
    """
    request_data = request.GET
    event = assessor_get_assessment_event_data(request_data, user=request.user)
    response_data = AssessmentEventSerializer(event).data
    return Response(data=response_data)


@require_POST
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def serve_grade_assessment_tool_attempts(request):
    """
    This view will serve as the end-point for assessors to grade their assessee's attempts on an AssessmentEvent
    The view will return the updated attempt data.
    ----------------------------------------------------------
    request-data must contain:
    tool-attempt-id: string
    grade: float
    note: string
    """
    request_data = json.loads(request.body.decode('utf-8'))
    updated_attempt = grade_assessment_tool(request_data, user=request.user)
    response_data = ToolAttemptSerializer(updated_attempt).data
    return Response(data=response_data, status=200)


@require_GET
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def serve_get_assignment_attempt_data(request):
    """
    This view will serve as the end-point for assessor to view the assessee submitted assignment data
    ----------------------------------------------------------
    request-data must contain:
    tool-attempt-id: string
    Format:
    assessment/review/assignment/data?tool-attempt-id=<ToolAttemptId>
    """
    request_data = request.GET
    assignment_attempt = get_assignment_attempt_data(request_data, user=request.user)
    response_data = AssignmentAttemptSerializer(assignment_attempt).data
    return Response(data=response_data, status=200)


@require_GET
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def serve_get_assignment_attempt_file(request):
    """
    This view will serve as the end-point for assessor to download the assessee submitted assignment
    ----------------------------------------------------------
    request-data must contain:
    tool-attempt-id: string
    Format:
    assessment/review/assignment/file?tool-attempt-id=<ToolAttemptId>
    """
    request_data = request.GET
    downloaded_file = get_assignment_attempt_file(request_data, user=request.user)

    if downloaded_file:
        return utils.generate_file_response(downloaded_file)
    else:
        return Response(data={'message': NO_ATTEMPT_FOUND}, status=200)


@require_POST
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def serve_update_assessment_event(request):
    """
    This view will serve as the end-point for assessor to update assessment events
    ----------------------------------------------------------
    request-data must contain:
    event_id: string
    request-data can contain:
    name: string
    start_date: date in ISO format
    test_flow_id: string
    """
    request_data = json.loads(request.body.decode('utf-8'))
    event = update_assessment_event(request_data, user=request.user)
    response_data = AssessmentEventSerializer(event).data
    return Response(data=response_data, status=200)


@require_POST
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def serve_delete_assessment_event(request):
    """
    This view will serve as the end-point for assessor to delete assessment events
    ----------------------------------------------------------
    request-data must contain:
    event_id: string
    """
    request_data = json.loads(request.body.decode('utf-8'))
    delete_assessment_event(request_data, user=request.user)
    return Response(data={'message': 'Assessment event has been deleted'}, status=200)


@require_POST
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def serve_grade_individual_question_attempts(request):
    """
    This view will serve as the end-point for assessors to grade their assessee's attempts on a single Interactive
    Quiz question
    ----------------------------------------------------------
    request-data must contain:
    tool-attempt-id: string
    question-attempt-id: string
    grade: float (text question) or is-correct: boolean (multiple choice question)
    note: string
    """
    request_data = json.loads(request.body.decode('utf-8'))
    grade, note = grade_interactive_quiz_individual_question(request_data, user=request.user)
    return Response(data={
        'message': f'Grade for question {request_data.get("question-attempt-id")} is saved',
        'grade': grade,
        'note': note}, status=200
    )


@require_POST
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def serve_save_graded_attempt(request):
    """
    This view will serve as the end-point for assessors to save the interactive quiz final grade after the
    assessor has finished grading
    ----------------------------------------------------------
    request-data must contain:
    tool-attempt-id: string
    """
    request_data = json.loads(request.body.decode('utf-8'))
    grade, note = grade_interactive_quiz(request_data, user=request.user)
    return Response(data={'message': 'Interactive Quiz grade saved successfully',
                          'grade': str(grade),
                          'note': note},
                    status=200)


@require_GET
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def serve_get_interactive_quiz_grading_data(request):
    """
    This view will serve as the end-point for assessor to view the assessee submitted quiz data
    ----------------------------------------------------------
    request-data must contain:
    tool-attempt-id: string
    Format:
    assessment/review/interactive-quiz/?tool-attempt-id=<ToolAttemptId>
    """
    request_data = request.GET
    response_data = get_interactive_quiz_grading_data(request_data, user=request.user)
    return Response(data=response_data, status=200)


@require_GET
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def serve_get_question_grading_data(request):
    """
        This view will serve as the end-point for assessor to view the assessee submitted individual question data
        ----------------------------------------------------------
        request-data must contain:
        tool-attempt-id: string
        question-attempt-id: string
        Format:
        assessment/review/individual-question/?tool-attempt-id=<ToolAttemptId>&question-attempt-id=<QuestionAttemptId>
        """
    request_data = request.GET
    response_data = get_question_grading_data(request_data, user=request.user)
    return Response(data=response_data, status=200)


@require_GET
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def serve_review_response_test_attempt_data(request):
    """
    This view will serve as the end-point for assessor to view the assessee submitted response-test
    attempt data.
    ----------------------------------------------------------
    request-data must contain:
    tool-attempt-id: string
    Format:
    assessment/review/response-test/?tool-attempt-id=<ToolAttemptId>
    """
    request_data = request.GET
    response_test_attempt = get_response_test_attempt_data(request_data, user=request.user)
    response_data = GradedResponseTestAttemptSerializer(response_test_attempt).data
    return Response(data=response_data, status=200)


@require_GET
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def serve_get_assessee_report_on_assessment_event(request):
    """
    This view will serve as the end-point for assessor to view the assessee report
    on assessment event.
    ----------------------------------------------------------
    request-data must contain:
    assessment-event-id: string
    assessee-email: string
    Format:
    assessment/review/response-test/?assessment-event-id=<AssessmentEventId>&assessee-email=<AssesseeEmail>
    """
    request_data = request.GET
    assessee_report = get_assessee_report_on_assessment_event(request_data, user=request.user)
    return Response(data=assessee_report, status=200)
