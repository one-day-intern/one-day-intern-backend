from rest_framework.views import exception_handler
from rest_framework.response import Response
from users.exceptions.exceptions import InvalidRegistrationException
from one_day_intern.exceptions import RestrictedAccessException, InvalidRequestException


def custom_exception_handler(exception, context):
    response = exception_handler(exception, context)
    if response is not None:
        return response

    if isinstance(exception, InvalidRegistrationException) or isinstance(exception, InvalidRequestException):
        status_code = 400
    elif isinstance(exception, RestrictedAccessException):
        status_code = 401
    else:
        status_code = 500

    return Response({'message': str(exception)}, status=status_code)

