from assessment.exceptions.exceptions import EventDoesNotExist
from assessment.models import (
    AssessmentEventParticipationSerializer,
    AssessmentEventSerializer,
    AssessmentEventParticipation,
    AssessmentEvent
)
from assessment.services.assessment_event_attempt import validate_assessor_participation
from assessment.services.utils import get_active_assessment_event_from_id
from assessment.services import utils as assessment_utils
from assessor.services import utils
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from one_day_intern.exceptions import InvalidRequestException, RestrictedAccessException
from users.models import AssesseeSerializer, Assessor, Assessee
from users.services import utils as users_utils


def get_assessment_event_participations(request_data: dict, user: User):
    try:
        event = get_active_assessment_event_from_id(request_data.get('assessment-event-id'))
        assessor = utils.get_assessor_or_company_from_user(user)
        validate_assessor_participation(event, assessor)
        event_participations = event.assessmenteventparticipation_set.filter(assessor=user)
        return event_participations

    except EventDoesNotExist as exception:
        raise InvalidRequestException(str(exception))


def get_assessor_assessment_events(user: User):
    found_user = utils.get_assessor_or_company_from_user(user)

    if type(found_user) == Assessor:
        event_participations = AssessmentEventParticipation.objects.filter(assessor=found_user).distinct('assessment_event')
        serialized_events = []

        for event_participation in event_participations:
            data = AssessmentEventSerializer(event_participation.assessment_event).data
            serialized_events.append(data)
    else:
        events = AssessmentEvent.objects.filter(owning_company=found_user)
        serialized_events = []

        for event in events:
            data = AssessmentEventSerializer(event).data
            serialized_events.append(data)

    return serialized_events


def get_all_active_assessees(request_data: dict, user: User):
    event_participations = get_assessment_event_participations(request_data, user)

    serialized_assessee_list = []

    for event_participation in event_participations:
        data = AssesseeSerializer(event_participation.assessee).data
        serialized_assessee_list.append(data)

    return serialized_assessee_list


def validate_assessee_participation(assessment_event: AssessmentEvent, assessee: Assessee):
    if not assessment_event.check_assessee_participation(assessee):
        raise InvalidRequestException(
            f'Assessee with email {assessee.email} is not part of assessment with id {assessment_event.event_id}'
        )


def validate_responsibility(event, assessor, assessee):
    if not event.check_assessee_and_assessor_pair(assessee, assessor):
        raise RestrictedAccessException(f'{assessor} is not responsible for {assessee} on event with id {event.event_id}')


def get_assessee_progress_on_assessment_event(request_data, user):
    try:
        assessor = users_utils.get_assessor_from_user(user)
    except ObjectDoesNotExist as exception:
        raise RestrictedAccessException(str(exception))

    try:
        event = assessment_utils.get_assessment_event_from_id(request_data.get('assessment-event-id'))
        validate_assessor_participation(event, assessor)
        assessee = assessment_utils.get_assessee_from_email(request_data.get('assessee-email'))
        validate_assessee_participation(event, assessee)
        validate_responsibility(event, assessor, assessee)
        return event.get_assessee_progress_on_event(assessee)
    except ObjectDoesNotExist as exception:
        raise InvalidRequestException(str(exception))

