from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from one_day_intern.exceptions import InvalidLoginCredentialsException
from . import utils


def verify_password(user: User, password: str):
    if not user.check_password(password):
        raise InvalidLoginCredentialsException(f'Password for {user.email} is invalid')


def get_assessor_or_company_from_request_data(request_data):
    try:
        return utils.get_assessor_or_company_from_email(request_data.get('email'))
    except ObjectDoesNotExist as exception:
        raise InvalidLoginCredentialsException(exception)


def login_assessor_company(request_data):
    return None
