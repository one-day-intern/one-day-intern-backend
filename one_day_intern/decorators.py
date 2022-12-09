from .exceptions import InvalidRequestException


def catch_exception_and_convert_to_invalid_request_decorator(exception_types: tuple):
    """
    This function is a decorator to service functions that need to convert
    ObjectDoesNotExist exception to InvalidRequestException.
    This decorator will catch ObjectDoesNotExist exceptions and raise
    an InvalidRequestException to be caught in the caller function.
    """
    def decorator(func_to_decorate):
        def decorated_function(*args, **kwargs):
            try:
                return func_to_decorate(*args, **kwargs)
            except exception_types as exception:
                raise InvalidRequestException(str(exception))
        return decorated_function
    return decorator

