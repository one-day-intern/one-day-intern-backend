from django.views.decorators.http import require_POST, require_GET
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .services.one_time_code import send_one_time_code_to_assessors
import json


@require_POST
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def serve_send_one_time_code_to_assessors(request):
    """
    request_data must contain
    assessor_emails
    Example valid request data
    {
        assessor_emails: [
            one-day-intern@gmail.com,
            one-day-intern@yahoo.com
        ]
    }
    """
    request_data = json.loads(request.body.decode('utf-8'))
    send_one_time_code_to_assessors(request_data, request.user)
    return Response(data={'message': 'Invitations has been sent'})


@require_GET
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def serve_get_company_assessors(request):
    """
    This view will serve as the end-point for assessor/company to get all registered
    assessors.
    ----------------------------------------------------------
    """
    return Response(data=None, status=200)