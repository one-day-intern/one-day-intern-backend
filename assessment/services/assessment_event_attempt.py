from users.models import Assessee
from .TaskGenerator import TaskGenerator
from ..models import AssessmentEvent


def validate_user_participation(assessment_event: AssessmentEvent, assessee: Assessee):
    return None


def subscribe_to_assessment_flow(request_data, user) -> TaskGenerator:
    return None
