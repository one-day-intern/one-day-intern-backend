from rest_framework.decorators import api_view, permission_classes
from django.views.decorators.http import require_POST
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .services.assessment import create_assignment
from .services.test_flow import create_test_flow
from .models import AssignmentSerializer, TestFlowSerializer
import json


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
                "release_time": <release-time>
            }
        ]
    }
    """
    request_data = json.loads(request.body.decode('utf-8'))
    test_flow = create_test_flow(request_data, user=request.user)
    response_data = TestFlowSerializer(test_flow).data
    return Response(data=response_data)

