from re import L


class RestrictedAccessException(Exception):
    pass


class InvalidRequestException(Exception):
    pass


class InvalidAssignmentRegistration(InvalidRequestException):
    pass


class InvalidInteractiveQuizRegistration(InvalidRequestException):
    pass


class InvalidRegistrationException(Exception):
    pass


class EmailNotFoundException(Exception):
    pass


class InvalidGoogleAuthCodeException(Exception):
    pass


class InvalidGoogleIDTokenException(Exception):
    pass


class InvalidGoogleLoginException(Exception):
    pass


class InvalidResponseTestRegistration(Exception):
    pass


class InvalidLoginCredentialsException(Exception):
    pass


class InvalidVideoConferenceNotificationException(Exception):
    pass