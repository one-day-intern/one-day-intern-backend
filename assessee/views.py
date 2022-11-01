from django.views.decorators.http import require_GET
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from assessment.models import AssessmentEventSerializer
from .services.assessee_assessment_events import get_assessee_assessment_events


@api_view(['GET'])
@require_GET
@permission_classes([IsAuthenticated])
def assessee_dashboard(request):

    return Response(data={
        'past_events': [],
        'current_events': [],
        'future_events': [],
    })


@api_view(['GET'])
@require_GET
@permission_classes([IsAuthenticated])
def serve_get_assessment_events_of_assessee(request):
    """
    This view will return all assessment events belonging to
    an assessee. When is-active is set to 'true', it will
    only return active events, and when it is set to 'false',
    it will return all assessment events regardless of the
    active status.
    ----------------------------------------------------------
    request-params must contain:
    is-active: string
    """
    find_active = request.GET.get('is-active')
    assessment_events = get_assessee_assessment_events(user=request.user, find_active=find_active)
    response_data = AssessmentEventSerializer(assessment_events, many=True).data
    return Response(data=response_data)
