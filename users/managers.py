# users/managers.py
from django.contrib.auth.models import BaseUserManager

class CustomerManager(BaseUserManager):
    def get_queryset(self):
        return super().get_queryset().filter(role='Customer')

class StaffManager(BaseUserManager):
    def get_queryset(self):
        return super().get_queryset().filter(role='Staff')
