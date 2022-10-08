from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _
from enum import Enum
from rest_framework import serializers
from .managers import OdiUserManager
import uuid


class OdiUser(AbstractUser):
    username = None
    first_name = None
    last_name = None
    email = models.EmailField(_('email address'), unique=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = OdiUserManager()

    class Meta:
        db_table = 'auth_user'

    def __str__(self):
        return self.email


class Company(OdiUser):
    company_id = models.UUIDField(default=uuid.uuid4, auto_created=True, null=False)
    company_name = models.CharField(max_length=50, null=False)
    description = models.TextField()
    address = models.TextField(null=False)


class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ['company_id', 'email', 'company_name', 'description', 'address']


class AuthenticationService(Enum):
    DEFAULT = 'default'
    GOOGLE = 'google'


class Assessor(OdiUser):
    first_name = models.CharField(max_length=50, null=False)
    last_name = models.CharField(max_length=50, null=True)
    phone_number = models.CharField(max_length=15, null=False)
    employee_id = models.CharField(max_length=50, null=True)
    associated_company = models.ForeignKey('Company', on_delete=models.CASCADE)
    authentication_service = models.CharField(
        max_length=120,
        choices=[(tag.value, tag.value) for tag in AuthenticationService],
        default=AuthenticationService.DEFAULT.value
    )


class AssessorSerializer(serializers.ModelSerializer):
    company_id = serializers.ReadOnlyField(source='associated_company.company_id')

    class Meta:
        model = Assessor
        fields = ['first_name', 'last_name', 'phone_number', 'employee_id', 'company_id']


class Assessee(OdiUser):
    first_name = models.CharField(max_length=50, null=False)
    last_name = models.CharField(max_length=50, null=True)
    phone_number = models.CharField(max_length=15, null=True)
    date_of_birth = models.DateField(null=True)
    authentication_service = models.CharField(
        max_length=120,
        choices=[(tag.value, tag.value) for tag in AuthenticationService],
        default=AuthenticationService.DEFAULT.value
    )

