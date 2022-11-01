from django.contrib.auth.models import User
from django.db.models import QuerySet

from assessment.exceptions.exceptions import EventDoesNotExist
from assessment.services.assessment_event_attempt import validate_assessor_participation
from assessment.services.utils import get_active_assessment_event_from_id
from assessor.services import utils
from one_day_intern.exceptions import InvalidRequestException
from users.models import AssesseeSerializer


def get_assessment_event_participations(request_data: dict, user: User):
    try:
        event = get_active_assessment_event_from_id(request_data.get('assessment-event-id'))
        assessor = utils.get_assessor_from_user(user)
        validate_assessor_participation(event, assessor)
        event_participations = event.assessmenteventparticipation_set.filter(assessor=user)
        return event_participations

    except EventDoesNotExist as exception:
        raise InvalidRequestException(str(exception))


def get_all_active_assessees(request_data: dict, user: User):
    event_participations = get_assessment_event_participations(request_data, user)

    serialized_assessee_list = []

    for event_participation in event_participations:
        data = AssesseeSerializer(event_participation.assessee).data
        serialized_assessee_list.append(data)

    return serialized_assessee_list
