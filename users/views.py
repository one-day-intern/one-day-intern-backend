from rest_framework.response import Response
from rest_framework.decorators import api_view
from .services.registration import register_company
from .models import CompanySerializer
import json


@api_view(['POST'])
def serve_register_company(request):
    """
        request_data must contain
        email,
        password,
        confirmed_password,
        company_name,
        company_description,
        company_address
    """
    request_data = json.loads(request.body.decode('utf-8'))
    company = register_company(request_data)
    response_data = CompanySerializer(company).data
    return Response(data=response_data)
