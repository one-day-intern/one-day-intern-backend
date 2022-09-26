from django.contrib.auth.base_user import BaseUserManager
from django.utils.translation import gettext_lazy as _


class OdiUserManager(BaseUserManager):
    def create_user(self, email, password, **extra_fields):
        return None

    def create_superuser(self, email, password):
        return None
