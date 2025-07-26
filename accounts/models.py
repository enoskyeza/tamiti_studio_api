# accounts/models.py
from django.db import models
from users.models import User
from core.models import BaseModel

class Department(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class Designation(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class Referral(models.Model):
    code = models.CharField(max_length=50)
    referrer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='referrals')


class StaffProfile(BaseModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='staff_profile')
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True)
    designation = models.ForeignKey(Designation, on_delete=models.SET_NULL, null=True)
    branch = models.CharField(max_length=100, null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_staff')


class CustomerProfile(BaseModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='customer_profile')
    referred_by = models.ForeignKey(Referral, on_delete=models.SET_NULL, null=True, blank=True)
