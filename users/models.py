# users/models.py
from django.contrib.auth.models import AbstractUser
from django.db import models
from .managers import CustomerManager, StaffManager

class User(AbstractUser):
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=15, unique=True, null=True, blank=True)
    is_verified = models.BooleanField(default=False)

    class Role(models.TextChoices):
        ADMIN = 'Admin'
        STAFF = 'Staff'
        CUSTOMER = 'Customer'

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.STAFF)

    REQUIRED_FIELDS = ['email', 'phone']
    USERNAME_FIELD = 'username'


class Customer(User):
    base_role = User.Role.CUSTOMER

    objects = CustomerManager()

    class Meta:
        proxy = True

    def save(self, *args, **kwargs):
        if not self.pk:
            self.role = self.base_role
        super().save(*args, **kwargs)


class Staff(User):
    base_role = User.Role.STAFF

    objects = StaffManager()

    class Meta:
        proxy = True

    def save(self, *args, **kwargs):
        if not self.pk:
            self.role = self.base_role
        super().save(*args, **kwargs)
