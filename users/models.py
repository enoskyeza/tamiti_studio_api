# users/models.py
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

from core.models import BaseModel
from .managers import CustomerManager, StaffManager

class User(AbstractUser):
    email = models.EmailField(unique=True, null=True, blank=True)
    phone = models.CharField(max_length=15, unique=True, null=True, blank=True)
    is_verified = models.BooleanField(default=False)
    # custom fields
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    bio = models.TextField(blank=True, null=True)
    total_tasks_completed = models.PositiveIntegerField(default=0)
    last_seen = models.DateTimeField(default=timezone.now)
    streak_days = models.PositiveIntegerField(default=0)
    current_streak_started = models.DateField(null=True, blank=True)
    
    # Temporary user support fields
    is_temporary = models.BooleanField(default=False, help_text="True if this is a temporary event-specific user")
    expires_at = models.DateTimeField(null=True, blank=True, help_text="When this temporary user expires")
    created_for_event = models.ForeignKey('ticketing.Event', null=True, blank=True, on_delete=models.CASCADE, related_name='temp_user_accounts')
    auto_generated_username = models.BooleanField(default=False, help_text="True if username was auto-generated")

    class Role(models.TextChoices):
        ADMIN = 'Admin'
        STAFF = 'Staff'
        CUSTOMER = 'Customer'
        SACCO_ADMIN = 'Sacco Admin'
        SACCO_MEMBER = 'Sacco Member'
        SACCO_SECRETARY = 'Sacco Secretary'

    role = models.CharField(max_length=30, choices=Role.choices, default=Role.STAFF)

    REQUIRED_FIELDS = []  # Remove required fields for temporary users
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
    
    def is_expired(self):
        """Check if this temporary user has expired"""
        if not self.is_temporary or not self.expires_at:
            return False
        return timezone.now() > self.expires_at
    
    def expires_in_days(self):
        """Get the number of days until this temporary user expires"""
        if not self.is_temporary or not self.expires_at:
            return None
        delta = self.expires_at - timezone.now()
        return max(0, delta.days)
    
    def clean(self):
        """Validate temporary user constraints"""
        from django.core.exceptions import ValidationError
        
        if self.is_temporary:
            if not self.expires_at:
                raise ValidationError("Temporary users must have an expiry date")
            if not self.created_for_event:
                raise ValidationError("Temporary users must be associated with an event")
        
        # Auto-generate email for temporary users if not provided
        if self.is_temporary and not self.email:
            self.email = f"{self.username}@temp.local"
    
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
    
    @classmethod
    def create_temporary_user(cls, event, username=None, password=None, expires_at=None, **extra_fields):
        """Create a temporary user for an event"""
        import secrets
        import string
        from datetime import timedelta
        
        if not username:
            # Auto-generate username
            username = f"temp_{event.id}_{secrets.token_hex(4)}"
            extra_fields['auto_generated_username'] = True
        
        if not password:
            # Auto-generate password
            password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))
        
        if not expires_at:
            # Default to 7 days from now
            expires_at = timezone.now() + timedelta(days=7)
        
        # Set default email if not provided in extra_fields
        if 'email' not in extra_fields:
            extra_fields['email'] = f"{username}@temp.local"
            
        user = cls.objects.create_user(
            username=username,
            password=password,
            is_temporary=True,
            expires_at=expires_at,
            created_for_event=event,
            **extra_fields
        )
        
        return user, password  # Return password for initial setup
    
    def get_sacco(self):
        """Get user's SACCO if they are a member"""
        if hasattr(self, 'sacco_membership'):
            return self.sacco_membership.sacco
        return None


class UserPreferences(BaseModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='preferences')
    dark_mode = models.BooleanField(default=True)
    language = models.CharField(max_length=20, default='en')
    timezone = models.CharField(max_length=50, default='Africa/Kampala', help_text='IANA timezone string')
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
