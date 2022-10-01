from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _
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

