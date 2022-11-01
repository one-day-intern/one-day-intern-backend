from django.contrib.auth.models import User
from users.models import Assessee
from assessment.services import utils as assessment_utils


def all_assessment_events(assessee: Assessee):
    assessment_event_participation_of_user = assessee.assessmenteventparticipation_set.all()
    assessment_events = [
        event_participation.assessment_event for event_participation in assessment_event_participation_of_user
    ]
    return assessment_events


def filter_active_assessment_events(assessment_events) -> list:
    active_assessment_events = []
    for assessment_event in assessment_events:
        if assessment_event.is_active():
            active_assessment_events.append(assessment_event)

    return active_assessment_events


def get_assessee_assessment_events(user: User, find_active):
    assessee = assessment_utils.get_assessee_from_user(user)
    assessment_events = all_assessment_events(assessee)

    if isinstance(find_active, str) and find_active.lower() == 'true':
        assessment_events = filter_active_assessment_events(assessment_events)

    return assessment_events
