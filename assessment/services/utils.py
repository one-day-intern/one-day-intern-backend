from django.contrib.auth.models import User
from datetime import time, datetime
from users.models import Company, Assessor
from one_day_intern.exceptions import RestrictedAccessException
from ..models import TestFlow
from ..exceptions.exceptions import AssessmentToolDoesNotExist, TestFlowDoesNotExist


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
