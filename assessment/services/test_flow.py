from django.contrib.auth.models import User
from one_day_intern import utils as odi_utils
from one_day_intern.exceptions import InvalidRequestException
from . import utils
from ..exceptions.exceptions import AssessmentToolDoesNotExist
from ..models import TestFlow


def validate_test_flow_registration(request_data: dict):
    if not odi_utils.text_value_is_valid(request_data.get('name'), max_length=50):
        raise InvalidRequestException('Test Flow name must exist and must be at most 50 characters')

    if request_data.get('tools_used') and not isinstance(request_data.get('tools_used'), list):
        raise InvalidRequestException('Test Flow must be of type list')

    if request_data.get('tools_used'):
        tools_used = request_data.get('tools_used')
        for tool_used_data in tools_used:
            tool_id = tool_used_data['tool_id']
            tool_release_time = tool_used_data['release_time']

            try:
                utils.get_tool_from_id(tool_id)
                utils.get_time_from_date_time_string(tool_release_time)
            except (ValueError, AssessmentToolDoesNotExist) as exception:
                raise InvalidRequestException(str(exception))


def convert_assessment_tool_id_to_assessment_tool(request_data) -> list:
    assessment_tools_in_request = request_data.get('tools_used')
    assessment_tools_release_time = []
    if assessment_tools_in_request:
        for request_tool_data in assessment_tools_in_request:
            tool = utils.get_tool_from_id(request_tool_data.get('tool_id'))
            release_time = utils.get_time_from_date_time_string(request_tool_data.get('release_time'))
            tool_data = {
                'tool': tool,
                'release_time': release_time
            }
            assessment_tools_release_time.append(tool_data)

    return assessment_tools_release_time


def save_test_flow_to_database(request_data, converted_tools, company) -> TestFlow:
    name = request_data.get('name')
    test_flow = TestFlow.objects.create(name=name, owning_company=company)

    for tool_data in converted_tools:
        test_flow.add_tool(
            assessment_tool=tool_data.get('tool'),
            release_time=tool_data.get('release_time')
        )

    return test_flow


def create_test_flow(request_data: dict, user: User):
    raise Exception
