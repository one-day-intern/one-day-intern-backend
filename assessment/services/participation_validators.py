from one_day_intern.exceptions import InvalidRequestException, RestrictedAccessException
from users.models import Assessee, Assessor
from ..models import AssessmentEvent


def validate_assessee_participation(assessment_event: AssessmentEvent, assessee: Assessee):
    if not assessment_event.check_assessee_participation(assessee):
        raise InvalidRequestException(
            f'Assessee with email {assessee.email} is not part of assessment with id {assessment_event.event_id}'
        )


def validate_assessor_participation(assessment_event: AssessmentEvent, assessor: Assessor):
    if not assessment_event.check_assessor_participation(assessor):
        raise RestrictedAccessException(
            f'Assessor with email {assessor.email} is not part of assessment with id {assessment_event.event_id}'
        )


def validate_user_participation(assessment_event: AssessmentEvent, assessee: Assessee):
    if not assessment_event.check_assessee_participation(assessee):
        raise RestrictedAccessException(
            f'Assessee with email {assessee.email} is not part of assessment with id {assessment_event.event_id}'
        )