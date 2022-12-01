from one_day_intern.exceptions import InvalidRequestException, RestrictedAccessException


def validate_grade_assessment_tool_request(request_data):
    if request_data.get('tool-attempt-id') is None:
        raise InvalidRequestException('Tool attempt id must exist')
    if request_data.get('grade') is not None and not isinstance(request_data.get('grade'), (float, int)):
        raise InvalidRequestException('Grade must be an integer or a floating point number')
    if request_data.get('note') is not None and not isinstance(request_data.get('note'), str):
        raise InvalidRequestException('Note must be a string')


def validate_assessor_responsibility(event, assessor, assessee):
    if not event.check_assessee_and_assessor_pair(assessee, assessor):
        raise RestrictedAccessException(f'{assessor} is not responsible for {assessee} on event with id {event.event_id}')


def set_grade_and_note_of_tool_attempt(tool_attempt, request_data):
    if request_data.get('grade'):
        tool_attempt.set_grade(request_data.get('grade'))

    if request_data.get('note'):
        tool_attempt.set_note(request_data.get('note'))