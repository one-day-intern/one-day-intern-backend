from rest_framework.response import Response
from rest_framework.decorators import api_view
from django.views.decorators.http import require_POST, require_GET
from django.shortcuts import redirect
from .services.registration import register_company, register_assessor, generate_one_time_code
from .services.google_login import (
    google_get_profile_from_id_token,
    google_get_id_token_from_auth_code,
    get_assessee_assessor_user_with_google_matching_data,
    get_tokens_for_user,
    register_assessee_with_google_data
)
from one_day_intern.settings import (
    GOOGLE_AUTH_LOGIN_REDIRECT_URI,
    GOOGLE_AUTH_REGISTER_ASSESSEE_REDIRECT_URI,
    GOOGLE_AUTH_CLIENT_CALLBACK_URL
)
from .models import CompanySerializer, AssessorSerializer, CompanyOneTimeLinkCodeSerializer
import json


@require_POST
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


@require_POST
@api_view(['POST'])
def serve_register_assessor(request):
    """
        request_data must contain
        email,
        password,
        confirmed_password,
        first_name,
        last_name,
        phone_number,
        employee_id,
        one_time_code
    """
    request_data = json.loads(request.body.decode('utf-8'))
    assessor = register_assessor(request_data)
    response_data = AssessorSerializer(assessor).data
    return Response(data=response_data)


@require_GET
@api_view(['GET'])
def serve_google_login_callback(request):
    auth_code = request.GET.get('code')
    id_token = google_get_id_token_from_auth_code(auth_code, GOOGLE_AUTH_LOGIN_REDIRECT_URI)
    user_profile = google_get_profile_from_id_token(id_token)
    user = get_assessee_assessor_user_with_google_matching_data(user_profile)
    tokens = get_tokens_for_user(user)

    response = redirect(GOOGLE_AUTH_CLIENT_CALLBACK_URL)
    response.set_cookie('accessToken', tokens.get('access'))
    response.set_cookie('refreshToken', tokens.get('refresh'))
    return response


@require_GET
@api_view(['GET'])
def serve_google_register_assessee(request):
    auth_code = request.GET.get('code')
    id_token = google_get_id_token_from_auth_code(auth_code, GOOGLE_AUTH_REGISTER_ASSESSEE_REDIRECT_URI)
    user_profile = google_get_profile_from_id_token(id_token)
    user = register_assessee_with_google_data(user_profile)
    tokens = get_tokens_for_user(user)

    response = redirect(GOOGLE_AUTH_CLIENT_CALLBACK_URL)
    response.set_cookie('accessToken', tokens.get('access'))
    response.set_cookie('refreshToken', tokens.get('refresh'))
    return response


@require_POST
@api_view(['POST'])
def generate_assessor_one_time_code(request):
    company_email = request.user.email
    one_time_code = generate_one_time_code(company_email)
    response_data = CompanyOneTimeLinkCodeSerializer(one_time_code).data
    return Response(data=response_data)
