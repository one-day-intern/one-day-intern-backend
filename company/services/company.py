from assessment.services import utils as assessment_utils
from django.contrib.auth.models import User
from one_day_intern.exceptions import RestrictedAccessException
from users.models import Company


def get_company_or_raise_exception(user: User):
    user_email = user.email
    found_companies = Company.objects.filter(email=user_email)
    if len(found_companies) > 0:
        return found_companies[0]
    else:
        raise RestrictedAccessException(f'User {user_email} is not a company')


def get_company_assessors(user):
    company = assessment_utils.get_company_or_assessor_associated_company_from_user(user)
    assessors = company.get_assessors()
    return assessors
