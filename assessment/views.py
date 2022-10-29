from django.core.exceptions import ObjectDoesNotExist
from django.views.decorators.http import require_POST, require_GET
from django.http.response import HttpResponse, StreamingHttpResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from assessment.services.assessment_tool import get_assessment_tool_by_company
from one_day_intern.exceptions import AuthorizationException, RestrictedAccessException
from users.services import utils as user_utils
from .services.assessment import create_assignment
from .services.test_flow import create_test_flow
from .services.assessment_event import create_assessment_event, add_assessment_event_participation
from .services.assessment_event_attempt import subscribe_to_assessment_flow
from .models import AssessmentToolSerializer, AssignmentSerializer, TestFlowSerializer, AssessmentEventSerializer
import json

@require_GET
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_assessment_tool(request):
    assignments = get_assessment_tool_by_company(request.user)
    response_data =[AssessmentToolSerializer(assignment).data for assignment in assignments]
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
    except AuthorizationException as exception:
        response_content = {'message': str(exception)}
        return HttpResponse(content=json.dumps(response_content), status=403)
    except RestrictedAccessException as exception:
        response_content = {'message': str(exception)}
        return HttpResponse(content=json.dumps(response_content), status=401)
    except ObjectDoesNotExist as exception:
        response_content = {'message': str(exception)}
        return HttpResponse(content=json.dumps(response_content), status=400)
    except Exception as exception:
        response_content = {'message': str(exception)}
        return HttpResponse(content=json.dumps(response_content), status=500)

