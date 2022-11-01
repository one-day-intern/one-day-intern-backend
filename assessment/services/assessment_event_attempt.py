from django.contrib.auth.models import User
from one_day_intern.exceptions import RestrictedAccessException, InvalidRequestException
from users.models import Assessee, Assessor
from ..exceptions.exceptions import EventDoesNotExist
from ..models import AssessmentEvent
from .TaskGenerator import TaskGenerator
from . import utils

ASSESEE_NOT_PART_OF_EVENT = 'Assessee with email {} is not part of assessment with id {}'


def validate_user_participation(assessment_event: AssessmentEvent, assessee: Assessee):
    if not assessment_event.check_assessee_participation(assessee):
        raise RestrictedAccessException(
            f'Assessee with email {assessee.email} is not part of assessment with id {assessment_event.event_id}'
        )


def validate_assessor_participation(assessment_event: AssessmentEvent, assessor: Assessor):
    if not assessment_event.check_assessor_participation(assessor):
        raise RestrictedAccessException(
            f'Assessor with email {assessor.email} is not part of assessment with id {assessment_event.event_id}'
        )


def subscribe_to_assessment_flow(request_data, user) -> TaskGenerator:
    event = utils.get_active_assessment_event_from_id(request_data.get('assessment-event-id'))
    assessee = utils.get_assessee_from_user(user)
    validate_user_participation(event, assessee)
    return event.get_task_generator()


def get_all_active_assignment(request_data: dict, user: User):
    try:
        event = utils.get_active_assessment_event_from_id(request_data.get('assessment-event-id'))
        assessee = utils.get_assessee_from_user(user)
        validate_user_participation(event, assessee)
        return event.get_released_assignments()
    except EventDoesNotExist as exception:
        raise InvalidRequestException(str(exception))


def verify_assessee_participation(request_data, user: User):
    assessee = utils.get_assessee_from_user(user)

    try:
        assessment_event = utils.get_assessment_event_from_id(request_data.get('assessment-event-id'))
    except EventDoesNotExist as exception:
        raise InvalidRequestException(str(exception))

    if not assessment_event.check_assessee_participation(assessee):
        raise RestrictedAccessException(ASSESEE_NOT_PART_OF_EVENT.format(assessee.email, assessment_event.event_id))
