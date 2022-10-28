from django.core.exceptions import ObjectDoesNotExist
from one_day_intern.exceptions import InvalidRequestException


class AssessmentToolDoesNotExist(ObjectDoesNotExist):
    pass


class InvalidTestFlowRegistration(InvalidRequestException):
    pass


class InvalidAssessmentEventRegistration(InvalidRequestException):
    pass
