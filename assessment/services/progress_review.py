from django.core.exceptions import ObjectDoesNotExist
from one_day_intern.exceptions import InvalidRequestException, RestrictedAccessException
from users.services import utils as users_utils
from .participation_validators import validate_assessor_participation, validate_assessee_participation
from . import utils


def validate_responsibility(event, assessor, assessee):
    if not event.check_assessee_and_assessor_pair(assessee, assessor):
        raise RestrictedAccessException(f'{assessor} is not responsible for {assessee} on event with id {event.event_id}')


def get_assessee_progress_on_assessment_event(request_data, user):
    try:
        assessor = users_utils.get_assessor_from_user(user)
    except ObjectDoesNotExist as exception:
        raise RestrictedAccessException(str(exception))

    try:
        event = utils.get_assessment_event_from_id(request_data.get('assessment-event-id'))
        validate_assessor_participation(event, assessor)
        assessee = utils.get_assessee_from_email(request_data.get('assessee-email'))
        validate_assessee_participation(event, assessee)
        validate_responsibility(event, assessor, assessee)
        return event.get_assessee_progress_on_event(assessee)
    except ObjectDoesNotExist as exception:
        raise InvalidRequestException(str(exception))