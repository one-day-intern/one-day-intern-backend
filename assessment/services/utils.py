from datetime import time, datetime
from ..exceptions.exceptions import AssessmentToolDoesNotExist
from ..models import AssessmentTool


def sanitize_file_format(file_format: str):
    if file_format:
        return file_format.strip('.')


def get_time_from_date_time_string(iso_datetime) -> time:
    iso_datetime = iso_datetime.strip('Z')
    try:
        datetime_: datetime = datetime.fromisoformat(iso_datetime)
        return time(datetime_.hour, datetime_.minute)
    except ValueError:
        raise ValueError(f'{iso_datetime} is not a valid ISO date string')


def get_tool_from_id(tool_id) -> AssessmentTool:
    found_assessment_tools = AssessmentTool.objects.filter(assessment_id=tool_id)

    if found_assessment_tools:
        return found_assessment_tools[0]
    else:
        raise AssessmentToolDoesNotExist(f'Assessment tool with id {tool_id} does not exist')

