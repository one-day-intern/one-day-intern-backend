from one_day_intern.exceptions import RestrictedAccessException, AuthorizationException
from users.models import Assessee
from .TaskGenerator import TaskGenerator
from ..models import AssessmentEvent
from . import utils


def validate_user_participation(assessment_event: AssessmentEvent, assessee: Assessee):
    if not assessment_event.check_assessee_participation(assessee):
        raise RestrictedAccessException(
            f'Assessee with email {assessee.email} is not part of assessment with id {assessment_event.event_id}'
        )


def subscribe_to_assessment_flow(request_data, user) -> TaskGenerator:
    event = utils.get_active_assessment_event_from_id(request_data.get('assessment-event-id'))
    assessee = utils.get_assessee_from_user(user)
    validate_user_participation(event, assessee)
    return event.get_task_generator()




