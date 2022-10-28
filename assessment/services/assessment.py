from django.contrib.auth.models import User
from users.models import Assessor
from . import utils
from ..models import Assignment, ResponseTest
from one_day_intern.exceptions import RestrictedAccessException, InvalidAssignmentRegistration, InvalidResponseTestRegistration


def get_assessor_or_raise_exception(user: User):
    user_email = user.email
    found_assessors = Assessor.objects.filter(email=user_email)
    if len(found_assessors) > 0:
        return found_assessors[0]
    else:
        raise RestrictedAccessException(f'User {user_email} is not an assessor')


def validate_assessment_tool(request_data):
    if not request_data.get('name'):
        raise InvalidAssignmentRegistration('Assessment name should not be empty')


def validate_assignment(request_data):
    if not request_data.get('duration_in_minutes'):
        raise InvalidAssignmentRegistration('Assignment should have duration')
    if not isinstance(request_data.get('duration_in_minutes'), int):
        raise InvalidAssignmentRegistration('Assignment duration must only be of type numeric')


def save_assignment_to_database(request_data: dict, assessor: Assessor):
    name = request_data.get('name')
    description = request_data.get('description')
    owning_company = assessor.associated_company
    expected_file_format = utils.sanitize_file_format(request_data.get('expected_file_format'))
    duration_in_minutes = request_data.get('duration_in_minutes')
    assignment = Assignment.objects.create(
        name=name,
        description=description,
        owning_company=owning_company,
        expected_file_format=expected_file_format,
        duration_in_minutes=duration_in_minutes
    )
    return assignment


def create_assignment(request_data, user):
    assessor = get_assessor_or_raise_exception(user)
    validate_assessment_tool(request_data)
    validate_assignment(request_data)
    assignment = save_assignment_to_database(request_data, assessor)
    return assignment

def validate_response_test(request_data):
    """
    response test MUST have subject and prompt
    """
    if len(request_data.get('prompt').split()) == 0:
        raise InvalidResponseTestRegistration('Prompt Should Not Be Empty')
    if len(request_data.get('subject').split()) == 0:
        raise InvalidResponseTestRegistration('Subject Should Not Be Empty')


def save_response_test_to_database(request_data: dict, assessor: Assessor):
    name = request_data.get('name')
    description = request_data.get('description')
    owning_company = assessor.associated_company
    prompt = request_data.get('prompt')
    subject = request_data.get('subject')
    sender = assessor
    assignment = ResponseTest.objects.create(
        name=name,
        description=description,
        owning_company=owning_company,
        prompt=prompt,
        subject=subject,
        sender=sender
    )
    return assignment


def create_response_test(request_data, user):
    assessor = get_assessor_or_raise_exception(user)
    validate_assessment_tool(request_data)
    validate_response_test(request_data)
    response_test = save_response_test_to_database(request_data, assessor)
    return response_test
