from django.contrib.auth.models import User
from one_day_intern.exceptions import RestrictedAccessException
from users.models import Assessor, Company


def get_assessor_or_company_from_user(user: User):
    found_assessors = Assessor.objects.filter(email=user.email)

    if found_assessors:
        return found_assessors[0]
    else:
        found_company = Company.objects.filter(email=user.email)
        if found_company:
            return found_company[0]
        else:
            raise RestrictedAccessException(f'User with email {user.email} is not an assessor')