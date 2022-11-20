from django.contrib.auth.models import User


def verify_password(user: User, password: str):
    raise Exception