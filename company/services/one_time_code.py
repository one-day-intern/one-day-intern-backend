from django.contrib.auth.models import User
from users.models import Company


def validate_request_data(request_data: dict):
    raise Exception


def generate_message(email: str, company: Company) -> tuple:
    return None


def email_one_time_code(request_data: str, company: Company):
    raise Exception


def send_one_time_code_to_assessors(request_data: dict, user: User):
    raise Exception


