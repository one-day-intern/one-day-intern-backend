from django.views.decorators.http import require_GET
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes


@api_view(['GET'])
@require_GET
@permission_classes([IsAuthenticated])
def assessee_dashboard(request):

    return Response(data={
        'past_events': [],
        'current_events': [],
        'future_events': [],
    })