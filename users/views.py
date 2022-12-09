from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from django.views.decorators.http import require_POST, require_GET
from django.shortcuts import redirect
from .services.registration import (
    register_company,
    register_assessor,
    generate_one_time_code,
    register_assessee
)
from .services.google_login import (
    google_get_profile_from_id_token,
    google_get_id_token_from_auth_code,
    get_tokens_for_user,
    login_or_register_assessee_with_google_data,
    register_assessor_with_google_data,
    get_assessor_user_with_google_matching_data
)
from .services.user_info import get_user_info
from .services import utils
from .services.login import login_assessee, login_assessor_company
from one_day_intern.settings import (
    GOOGLE_AUTH_LOGIN_REGISTER_ASSESSEE_REDIRECT_URI,
    GOOGLE_AUTH_LOGIN_ASSESSOR_REDIRECT_URI,
    GOOGLE_AUTH_REGISTER_ASSESSOR_REDIRECT_URI,
    GOOGLE_AUTH_CLIENT_ASSESSEE_CALLBACK_URL,
    GOOGLE_AUTH_CLIENT_ASSESSOR_CALLBACK_URL
)
from .models import (
    CompanySerializer,
    AssessorSerializer,
    CompanyOneTimeLinkCodeSerializer,
    AssesseeSerializer
)
import json


@require_GET
@api_view(['GET'])
def serve_google_register_assessor(request):
    auth_code = request.GET.get('code')
    otc_data = {'one_time_code': request.GET.get('state')}
    try:
        id_token = google_get_id_token_from_auth_code(auth_code, GOOGLE_AUTH_REGISTER_ASSESSOR_REDIRECT_URI)
        user_profile = google_get_profile_from_id_token(id_token)
        user = register_assessor_with_google_data(user_profile, otc_data)
        tokens = get_tokens_for_user(user)
        param_argument = {
            'accessToken': tokens.get('access'),
            'refreshToken': tokens.get('refresh')
        }
        parameterized_url = utils.parameterize_url(GOOGLE_AUTH_CLIENT_ASSESSEE_CALLBACK_URL + '/?', param_argument)
        response = redirect(parameterized_url)
    except Exception as exception:
        param_argument = {'errorMessage': str(exception)}
        parameterized_url = utils.parameterize_url(GOOGLE_AUTH_CLIENT_ASSESSEE_CALLBACK_URL + '/?', param_argument)
        response = redirect(parameterized_url)

    return response


@require_GET
@api_view(['GET'])
def serve_google_login_callback_for_assessor(request):
    """
    This view will serve as the callback for the Assessor Google login.
    An authcode is expected to be present in the request argument.
    ----------------------------------------------------------
    request-param must contain:
    code: string
    """
    auth_code = request.GET.get('code')
    try:
        id_token = google_get_id_token_from_auth_code(auth_code, GOOGLE_AUTH_LOGIN_ASSESSOR_REDIRECT_URI)
        user_profile = google_get_profile_from_id_token(id_token)
        user = get_assessor_user_with_google_matching_data(user_profile)
        tokens = get_tokens_for_user(user)
        param_argument = {
            'accessToken': tokens.get('access'),
            'refreshToken': tokens.get('refresh')
        }
        parameterized_url = utils.parameterize_url(GOOGLE_AUTH_CLIENT_ASSESSEE_CALLBACK_URL + '/?', param_argument)
        response = redirect(parameterized_url)
    except Exception as exception:
        param_argument = {'errorMessage': str(exception)}
        parameterized_url = utils.parameterize_url(GOOGLE_AUTH_CLIENT_ASSESSEE_CALLBACK_URL + '/?', param_argument)
        response = redirect(parameterized_url)

    return response


@require_GET
@api_view(['GET'])
def serve_google_login_register_assessee(request):
    auth_code = request.GET.get('code')
    try:
        id_token = google_get_id_token_from_auth_code(auth_code, GOOGLE_AUTH_LOGIN_REGISTER_ASSESSEE_REDIRECT_URI)
        user_profile = google_get_profile_from_id_token(id_token)
        user = login_or_register_assessee_with_google_data(user_profile)
        tokens = get_tokens_for_user(user)
        param_argument = {
            'accessToken': tokens.get('access'),
            'refreshToken': tokens.get('refresh')
        }
        parameterized_url = utils.parameterize_url(GOOGLE_AUTH_CLIENT_ASSESSEE_CALLBACK_URL + '/?', param_argument)
        response = redirect(parameterized_url)
    except Exception as exception:
        param_argument = {'errorMessage': str(exception)}
        parameterized_url = utils.parameterize_url(GOOGLE_AUTH_CLIENT_ASSESSEE_CALLBACK_URL + '/?', param_argument)
        response = redirect(parameterized_url)

    return response


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


@require_POST
@api_view(['POST'])
def serve_register_assessee(request):
    """
        request_data must contain
        email,
        password,
        confirmed_password,
        first_name,
        last_name,
        phone_number,
        date_of_birth,
    """
    request_data = json.loads(request.body.decode('utf-8'))
    assessee = register_assessee(request_data)
    response_data = AssesseeSerializer(assessee).data
    return Response(data=response_data)


@require_POST
@api_view(['POST'])
def serve_register_assessee(request):
    """
        request_data must contain
        email,
        password,
        confirmed_password,
        first_name,
        last_name,
        phone_number,
        date_of_birth,
    """
    request_data = json.loads(request.body.decode('utf-8'))
    assessee = register_assessee(request_data)
    response_data = AssesseeSerializer(assessee).data
    return Response(data=response_data)


@require_POST
@api_view(['POST'])
def serve_login_assessor_company(request):
    """
    This view will return the refresh and access token for an assessor or company.
    ----------------------------------------------------------
    request-data must contain:
    email: string
    password: string
    """
    request_data = json.loads(request.body.decode('utf-8'))
    token = login_assessor_company(request_data)
    return Response(data=token, status=200)


@require_POST
@api_view(['POST'])
def generate_assessor_one_time_code(request):
    company_email = request.user.email
    one_time_code = generate_one_time_code(company_email)
    response_data = CompanyOneTimeLinkCodeSerializer(one_time_code).data
    return Response(data=response_data)


@require_GET
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def serve_get_user_info(request):
    response_data = get_user_info(request.user)
    return Response(data=response_data)


@require_POST
@api_view(['POST'])
def serve_login_assessor_company(request):
    """
    This view will return the refresh and access token for an assessor or company.
    ----------------------------------------------------------
    request-data must contain:
    email: string
    password: string
    """
    request_data = json.loads(request.body.decode('utf-8'))
    token = login_assessor_company(request_data)
    return Response(data=token, status=200)


@require_POST
@api_view(['POST'])
def serve_login_assessee(request):
    """
    This view will return the refresh and access token for an assessee.
    ----------------------------------------------------------
    request-data must contain:
    email: string
    password: string
    """
    request_data = json.loads(request.body.decode('utf-8'))
    token = login_assessee(request_data)
    return Response(data=token, status=200)