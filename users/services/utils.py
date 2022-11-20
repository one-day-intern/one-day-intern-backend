from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ObjectDoesNotExist
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken
from datetime import datetime
from typing import Optional, Match
from ..models import Assessor, Company
import phonenumbers
import re

DATETIME_FORMAT = '%Y-%m-%d'
email_regex = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'


def validate_password(password) -> dict:
    validation_result = {
        'is_valid': True,
        'message': None
    }
    if len(password) < 8:
        validation_result['is_valid'] = False
        validation_result['message'] = 'Password length must be at least 8 characters'
    elif not any(character.isupper() for character in password):
        validation_result['is_valid'] = False
        validation_result['message'] = 'Password length must contain at least 1 uppercase character'
    elif not any(character.islower() for character in password):
        validation_result['is_valid'] = False
        validation_result['message'] = 'Password length must contain at least 1 lowercase character'
    elif not any(character.isdigit() for character in password):
        validation_result['is_valid'] = False
        validation_result['message'] = 'Password length must contain at least 1 number character'
    return validation_result


def validate_email(email) -> Optional[Match[str]]:
    return re.fullmatch(email_regex, email)


def validate_date_format(date_text) -> bool:
    date_text = date_text.split('T')[0]
    try:
        datetime.strptime(date_text, DATETIME_FORMAT)
        return True
    except ValueError:
        return False


def validate_phone_number(phone_number_string) -> bool:
    phone_number = phonenumbers.parse(phone_number_string)
    return phonenumbers.is_possible_number(phone_number)


def get_date_from_string(date_text):
    date_text = date_text.split('T')[0]
    date_text_datetime = datetime.strptime(date_text, DATETIME_FORMAT)
    return date_text_datetime.date()


def sanitize_request_data(request_data):
    for key, value in request_data.items():
        if isinstance(value, str):
            request_data[key] = value.strip()


def parameterize_url(base_url, parameter_arguments):
    parameterized_url = base_url
    for param, argument in parameter_arguments.items():
        if argument:
            search_param = param + '=' + str(argument)
        else:
            search_param = param
        parameterized_url += search_param + '&'
    return parameterized_url


def get_user_from_request(request):
    jwt_authenticator = JWTAuthentication()
    try:
        response = jwt_authenticator.authenticate(request)
        user, token = response
        return user
    except InvalidToken:
        return AnonymousUser()


def get_assessor_from_email(email):
    try:
        return Assessor.objects.get(email=email)
    except ObjectDoesNotExist:
        raise ObjectDoesNotExist(f'Assessor with email {email} not found')


def get_company_from_email(email):
    try:
        return Company.objects.get(email=email)
    except ObjectDoesNotExist:
        raise ObjectDoesNotExist(f'Company with email {email} not found')