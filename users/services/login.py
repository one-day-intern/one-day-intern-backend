from django.contrib.auth.models import User
from one_day_intern.exceptions import InvalidLoginCredentialsException


def verify_password(user: User, password: str):
    if not user.check_password(password):
        raise InvalidLoginCredentialsException(f'Password for {user.email} is invalid')