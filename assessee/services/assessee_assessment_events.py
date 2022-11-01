from users.models import Assessee


def all_assessment_events(assessee: Assessee):
    assessment_event_participation_of_user = assessee.assessmenteventparticipation_set.all()
    assessment_events = [
        event_participation.assessment_event for event_participation in assessment_event_participation_of_user
    ]
    return assessment_events


def filter_active_assessment_events(assessment_events) -> list:
    return None
