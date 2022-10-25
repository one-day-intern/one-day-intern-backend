from django.contrib.auth.models import User
from ..models import TestFlow


def validate_test_flow_registration(request_data: dict):
    raise Exception


def convert_assessment_tool_id_to_assessment_tool(request_data) -> list:
    raise Exception


def save_test_flow_to_database(request_data, converted_tools, company) -> TestFlow:
    raise Exception


def create_test_flow(request_data: dict, user: User):
    raise Exception
