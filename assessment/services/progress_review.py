from django.core.exceptions import ObjectDoesNotExist
from one_day_intern.decorators import catch_exception_and_convert_to_invalid_request_decorator
from one_day_intern.exceptions import InvalidRequestException, RestrictedAccessException
from users.services import utils as users_utils
from .participation_validators import validate_assessor_participation, validate_assessee_participation
from . import utils


def validate_responsibility(event, assessor, assessee):
    if not event.check_assessee_and_assessor_pair(assessee, assessor):
        raise RestrictedAccessException(f'{assessor} is not responsible for {assessee} on event with id {event.event_id}')


@catch_exception_and_convert_to_invalid_request_decorator(exception_types=ObjectDoesNotExist)
def get_assessee_progress_on_assessment_event(request_data, user):
    try:
        assessor = users_utils.get_assessor_from_user(user)
    except ObjectDoesNotExist as exception:
        raise RestrictedAccessException(str(exception))

    event = utils.get_assessment_event_from_id(request_data.get('assessment-event-id'))
    validate_assessor_participation(event, assessor)
    assessee = utils.get_assessee_from_email(request_data.get('assessee-email'))
    validate_assessee_participation(event, assessee)
    validate_responsibility(event, assessor, assessee)
    return event.get_assessee_progress_on_event(assessee)


@catch_exception_and_convert_to_invalid_request_decorator(exception_types=ObjectDoesNotExist)
def get_assessee_report_on_assessment_event(request_data, user):
    try:
        assessor = users_utils.get_assessor_from_user(user)
    except ObjectDoesNotExist as exception:
        raise RestrictedAccessException(str(exception))

    event = utils.get_assessment_event_from_id(request_data.get('assessment-event-id'))
    assessee = utils.get_assessee_from_email(request_data.get('assessee-email'))
    validate_responsibility(event, assessor, assessee)
    return event.get_event_report_of_assessee(assessee)


@catch_exception_and_convert_to_invalid_request_decorator(exception_types=ObjectDoesNotExist)
def assessor_get_assessment_event_data(request_data, user):
    try:
        assessor = users_utils.get_assessor_from_user(user)
    except ObjectDoesNotExist as exception:
        raise RestrictedAccessException(str(exception))

    event = utils.get_assessment_event_from_id(request_data.get('assessment-event-id'))
    validate_assessor_participation(event, assessor)
    return event
