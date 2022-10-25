from ..models import AssessmentTool
from datetime import time


def sanitize_file_format(file_format: str):
    if file_format:
        return file_format.strip('.')


def get_time_from_date_time_string(iso_datetime) -> time:
    return None


def get_tool_from_id(tool_id) -> AssessmentTool:
    return None

