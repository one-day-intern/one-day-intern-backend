from django.views.decorators.http import require_GET
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from .services.dashboard import (
    get_all_active_assessees,
    get_assessor_assessment_events,
    get_assessee_progress_on_assessment_event
)


@api_view(['GET'])
@require_GET
@permission_classes([IsAuthenticated])
def assessor_dashboard(request):

    return Response(data={
        'test_flows': [],
        'list_of_assessees': [],
    })


@require_GET
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def serve_get_all_assessment_events(request):
    """
    Endpoint that can only be accessed by assessor.
    Assessor authentication-related information should be present through the JWT.
    URL structure /assessment-event-list/
    """
    assessment_events = get_assessor_assessment_events(user=request.user)
    return Response(data=assessment_events)


@require_GET
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def serve_get_all_active_assessees(request):
    """
    Endpoint that can only be accessed by assessor.
    Assessor authentication-related information should be present through the JWT.
    URL structure /assessee-list/?assessment-event-id=<assessment-event-id>
    """
    request_data = request.GET
    active_assessees = get_all_active_assessees(request_data, user=request.user)
    return Response(data=active_assessees)


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

