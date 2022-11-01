from django.contrib.auth.models import User

from one_day_intern.exceptions import AuthorizationException
from users.models import Assessor


def get_assessor_from_user(user: User) -> Assessor:
    found_assessors = Assessor.objects.filter(email=user.email)

    if found_assessors:
        return found_assessors[0]
    else:
        raise AuthorizationException(f'User with email {user.email} is not an assessor')