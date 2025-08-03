# accounts/models.py
from django.db import models
from users.models import User, Tag
from core.models import BaseModel

class Department(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class Designation(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class Branch(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class Referral(models.Model):
    code = models.CharField(max_length=50)
    referrer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='referrals')


class StaffRole(BaseModel):
    title = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    dashboard_url = models.URLField(blank=True, null=True)
    tags = models.ManyToManyField(Tag, blank=True)
    is_virtual = models.BooleanField(default=False)
    prompt_context = models.TextField(blank=True, help_text="Optional instructions if used as virtual assistant")

    def __str__(self):
        return self.title


class StaffProfile(BaseModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='staff_profile', null=True, blank=True)
    name = models.CharField(max_length=255, blank=True, help_text="Only used for virtual assistants or aliases")
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True)
    designation = models.ForeignKey(Designation, on_delete=models.SET_NULL, null=True)
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True)
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_staff')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_staff')
    role = models.ForeignKey('StaffRole', on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return self.name or self.user.get_full_name() if self.user else "[Unlinked Staff]"

class CustomerProfile(BaseModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='customer_profile')
    referred_by = models.ForeignKey(Referral, on_delete=models.SET_NULL, null=True, blank=True)