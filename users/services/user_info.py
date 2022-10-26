from django.contrib.auth.models import User
from ..models import (
    Assessor,
    Assessee,
    Company,
    AssessorSerializer,
    AssesseeSerializer,
    CompanySerializer
)


def get_user_info(user: User):
    if found_company := Company.objects.filter(email=user.email):
        return CompanySerializer(found_company[0]).data
    elif found_assessor := Assessor.objects.filter(email=user.email):
        return AssessorSerializer(found_assessor[0]).data
    else:
        found_assessee = Assessee.objects.filter(email=user.email)
        return AssesseeSerializer(found_assessee[0]).data

