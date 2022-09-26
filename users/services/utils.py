from datetime import datetime


def validate_password(password) -> dict:
    return {
        'is_valid': False,
        'message': None
    }


def validate_email(email) -> bool:
    return False


def validate_date_format(date_str) -> bool:
    return False


def get_date_from_string(date_str):
    return datetime.now()
