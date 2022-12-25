from django.core.exceptions import ObjectDoesNotExist
from one_day_intern.exceptions import InvalidRequestException


class AssessmentToolDoesNotExist(ObjectDoesNotExist):
    pass


class InvalidTestFlowRegistration(InvalidRequestException):
    pass


class InvalidAssessmentEventRegistration(InvalidRequestException):
    pass


class TestFlowDoesNotExist(ObjectDoesNotExist):
    pass


class EventDoesNotExist(ObjectDoesNotExist):
    pass


class AssessmentToolDoesNotExist(ObjectDoesNotExist):
    pass


class QuestionDoesNotExist(ObjectDoesNotExist):
    pass


class QuestionAttemptDoesNotExist(ObjectDoesNotExist):
    pass
