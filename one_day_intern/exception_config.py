from rest_framework.views import exception_handler
from rest_framework.response import Response
from users.exceptions.exceptions import InvalidRegistrationException


def custom_exception_handler(exception, context):
    response = exception_handler(exception, context)
    if response is not None:
        return response

    if isinstance(exception, InvalidRegistrationException):
        status_code = 400
    else:
        status_code = 500

    return Response({'message': str(exception)}, status=status_code)

