from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth.models import User
from datetime import time, datetime
from users.models import Company, Assessor, Assessee
from one_day_intern.exceptions import RestrictedAccessException
from ..models import TestFlow, AssessmentEvent, ToolAttempt
from ..exceptions.exceptions import AssessmentToolDoesNotExist, TestFlowDoesNotExist, EventDoesNotExist


def sanitize_file_format(file_format: str):
    if file_format:
        return file_format.strip('.')


def get_interactive_quiz_total_points(questions):
    total_points = 0
    for q in questions:
        total_points += q.get('points')

    return total_points


def get_time_from_date_time_string(iso_datetime) -> time:
    iso_datetime = iso_datetime.strip('Z') if iso_datetime else None
    try:
        datetime_: datetime = datetime.fromisoformat(iso_datetime)
        return time(datetime_.hour, datetime_.minute)
    except (ValueError, TypeError):
        raise ValueError(f'{iso_datetime} is not a valid ISO date string')


def get_tool_of_company_from_id(tool_id: str, owning_company: Company):
    found_assessment_tools = owning_company.assessmenttool_set.filter(assessment_id=tool_id)

    if found_assessment_tools:
        return found_assessment_tools[0]
    else:
        raise AssessmentToolDoesNotExist(
            f'Assessment tool with id {tool_id} belonging to company {owning_company.company_name} does not exist'
        )


def get_company_or_assessor_associated_company_from_user(user: User) -> Company:
    found_companies = Company.objects.filter(email=user.email)
    if found_companies:
        return found_companies[0]

    found_assessors = Assessor.objects.filter(email=user.email)
    if found_assessors:
        assessor = found_assessors[0]
        return assessor.associated_company

    raise RestrictedAccessException(f'User with email {user.email} is not a company or an assessor')


def get_date_from_date_time_string(iso_datetime):
    iso_datetime = iso_datetime.strip('Z')
    try:
        datetime_: datetime = datetime.fromisoformat(iso_datetime)
        return datetime_
    except ValueError:
        raise ValueError(f'{iso_datetime} is not a valid ISO date string')


def get_active_test_flow_of_company_from_id(test_flow_id, owning_company) -> TestFlow:
    found_test_flows = owning_company.testflow_set.filter(test_flow_id=test_flow_id, is_usable=True)

    if found_test_flows:
        return found_test_flows[0]
    else:
        raise TestFlowDoesNotExist(
            f'Active test flow of id {test_flow_id} belonging to {owning_company.company_name} does not exist'
        )


def get_assessee_from_email(email):
    try:
        return Assessee.objects.get(email=email.lower())
    except ObjectDoesNotExist:
        raise ObjectDoesNotExist(f'Assessee with email {email} not found')


def get_company_assessor_from_email(email, company: Company):
    found_assessors = company.assessor_set.filter(email=email.lower())

    if found_assessors:
        return found_assessors[0]
    else:
        raise ObjectDoesNotExist(f'Assessor with email {email} associated with {company.company_name} is not found')


def get_assessment_event_from_id(assessment_event_id) -> AssessmentEvent:
    found_events = AssessmentEvent.objects.filter(event_id=assessment_event_id)

    if found_events:
        return found_events[0]
    else:
        raise EventDoesNotExist(f'Assessment Event with ID {assessment_event_id} does not exist')


def get_active_assessment_event_from_id(event_id):
    found_events = AssessmentEvent.objects.filter(event_id=event_id)

    if found_events:
        found_event: AssessmentEvent = found_events[0]
    else:
        raise EventDoesNotExist(f'Assessment Event with ID {event_id} does not exist')

    if found_event.is_active():
        return found_event
    else:
        raise EventDoesNotExist(f'Assessment Event with ID {event_id} is not active')


def get_assessee_from_user(user: User) -> Assessee:
    found_assessees = Assessee.objects.filter(email=user.email)

    if found_assessees:
        return found_assessees[0]
    else:
        raise RestrictedAccessException(f'User with email {user.email} is not an assessee')


def get_prefix_from_file_name(file_name):
    try:
        prefix = file_name.split('.')[1]
        return prefix
    except IndexError:
        raise ValueError(f'{file_name} is not a proper file name')


def get_tool_attempt_from_id(tool_attempt_id) -> ToolAttempt:
    try:
        tool_attempt = ToolAttempt.objects.get(tool_attempt_id=tool_attempt_id)
        return tool_attempt
    except ObjectDoesNotExist:
        raise ObjectDoesNotExist(f'Tool attempt with id {tool_attempt_id} does not exist')
