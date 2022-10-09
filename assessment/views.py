from rest_framework.decorators import api_view, permission_classes
from django.views.decorators.http import require_POST
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .services.assessment import create_assignment
from .models import AssignmentSerializer
import json


@require_POST
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def serve_create_assignment(request):
    """
    request_data must contain
    assignment_name (string),
    description (string),
    duration_in_minutes (integer),
    expected_file_format (string, without leading .)
    """
    request_data = json.loads(request.body.decode('utf-8'))
    assignment = create_assignment(request_data, request.user)
    response_data = AssignmentSerializer(assignment).data
    return Response(data=response_data)
