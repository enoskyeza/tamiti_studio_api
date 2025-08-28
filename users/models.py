# users/models.py
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

from core.models import BaseModel
from .managers import CustomerManager, StaffManager

class User(AbstractUser):
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=15, unique=True, null=True, blank=True)
    is_verified = models.BooleanField(default=False)
    # custom fields
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    bio = models.TextField(blank=True, null=True)
    total_tasks_completed = models.PositiveIntegerField(default=0)
    last_seen = models.DateTimeField(default=timezone.now)
    streak_days = models.PositiveIntegerField(default=0)
    current_streak_started = models.DateField(null=True, blank=True)

    class Role(models.TextChoices):
        ADMIN = 'Admin'
        STAFF = 'Staff'
        CUSTOMER = 'Customer'

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.STAFF)

    REQUIRED_FIELDS = ['email', 'phone']
    USERNAME_FIELD = 'username'

    def update_last_seen(self):
        self.last_seen = timezone.now()
        self.save(update_fields=['last_seen'])

    def update_streak(self):
        today = timezone.now().date()
        if self.current_streak_started == today:
            return
        if self.current_streak_started == today - timezone.timedelta(days=1):
            self.streak_days += 1
        else:
            self.streak_days = 1
        self.current_streak_started = today
        self.save(update_fields=['streak_days', 'current_streak_started'])


class UserPreferences(BaseModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='preferences')
    dark_mode = models.BooleanField(default=True)
    language = models.CharField(max_length=20, default='en')
    daily_summary = models.BooleanField(default=True)

    def __str__(self):
        return f"Preferences for {self.user.username}"


class Tag(BaseModel):
    label = models.CharField(max_length=50, unique=True)
    color = models.CharField(max_length=10, default='#000000')  # For UI

    def __str__(self):
        return self.label


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
