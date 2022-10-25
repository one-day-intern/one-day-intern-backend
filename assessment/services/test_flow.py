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
    raise Exception


def save_test_flow_to_database(request_data, converted_tools, company) -> TestFlow:
    raise Exception


def create_test_flow(request_data: dict, user: User):
    raise Exception
