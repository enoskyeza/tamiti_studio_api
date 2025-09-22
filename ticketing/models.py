import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
import secrets
import string
from core.models import BaseModel


class Event(BaseModel):
    """Events for which tickets can be generated"""
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('ended', 'Ended'),
        ('cancelled', 'Cancelled'),
    ]
    
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    date = models.DateTimeField()
    venue = models.CharField(max_length=200)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='created_events')
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name




class TicketType(BaseModel):
    """Different types of tickets for an event"""
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='ticket_types')
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(blank=True)
    max_quantity = models.PositiveIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ['event', 'name']
        ordering = ['price']
    
    def __str__(self):
        return f"{self.event.name} - {self.name}"


class Batch(BaseModel):
    """A batch of QR codes generated for an event"""
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('partially_used', 'Partially Used'),
        ('void', 'Void'),
    ]
    
    batch_number = models.CharField(max_length=20, unique=True)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='batches')
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(10000)])
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='created_batches')
    voided_at = models.DateTimeField(null=True, blank=True)
    voided_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='voided_batches')
    void_reason = models.TextField(blank=True)
    
    # Layout configuration
    layout_columns = models.PositiveIntegerField(default=5, validators=[MinValueValidator(1), MaxValueValidator(20)])
    layout_rows = models.PositiveIntegerField(default=10, validators=[MinValueValidator(1), MaxValueValidator(50)])
    qr_size = models.PositiveIntegerField(default=25, validators=[MinValueValidator(10), MaxValueValidator(50)], help_text="QR code size in mm")
    include_short_code = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Batch {self.batch_number} - {self.event.name}"
    
    def save(self, *args, **kwargs):
        if not self.batch_number:
            self.batch_number = self.generate_batch_number()
        super().save(*args, **kwargs)
    
    def generate_batch_number(self):
        """Generate a unique batch number"""
        timestamp = timezone.now().strftime('%y%m%d')
        random_suffix = ''.join(secrets.choice(string.digits) for _ in range(4))
        return f"B{timestamp}{random_suffix}"
    
    @property
    def activated_count(self):
        return self.tickets.filter(status__in=['activated', 'scanned']).count()
    
    @property
    def scanned_count(self):
        return self.tickets.filter(status='scanned').count()
    
    @property
    def voided_count(self):
        return self.tickets.filter(status='void').count()
    
    @property
    def unused_count(self):
        return self.tickets.filter(status='unused').count()


class Ticket(BaseModel):
    """Individual ticket/code"""
    STATUS_CHOICES = [
        ('unused', 'Unused'),
        ('activated', 'Activated'),
        ('scanned', 'Scanned'),
        ('void', 'Void'),
    ]
    
    batch = models.ForeignKey(Batch, on_delete=models.CASCADE, related_name='tickets')
    short_code = models.CharField(max_length=10, unique=True)
    qr_code = models.CharField(max_length=255, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='unused')
    
    # Buyer information (optional)
    buyer_name = models.CharField(max_length=200, blank=True)
    buyer_phone = models.CharField(max_length=20, blank=True)
    buyer_email = models.EmailField(blank=True)
    ticket_type = models.ForeignKey(TicketType, on_delete=models.SET_NULL, null=True, blank=True)
    notes = models.TextField(blank=True)
    
    # Activation info
    activated_at = models.DateTimeField(null=True, blank=True)
    activated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='activated_tickets')
    
    # Scanning info
    scanned_at = models.DateTimeField(null=True, blank=True)
    scanned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='scanned_tickets')
    gate = models.CharField(max_length=50, blank=True)
    
    class Meta:
        ordering = ['short_code']
        indexes = [
            models.Index(fields=['qr_code']),
            models.Index(fields=['short_code']),
            models.Index(fields=['status']),
            models.Index(fields=['batch', 'status']),
        ]
    
    def __str__(self):
        return f"Ticket {self.short_code} - {self.batch.event.name}"
    
    def save(self, *args, **kwargs):
        if not self.short_code:
            self.short_code = self.generate_short_code()
        if not self.qr_code:
            self.qr_code = self.generate_qr_code()
        super().save(*args, **kwargs)
    
    def generate_short_code(self):
        """Generate a unique short code for manual entry"""
        while True:
            code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
            if not Ticket.objects.filter(short_code=code).exists():
                return code
    
    def generate_qr_code(self):
        """Generate a unique QR code string"""
        while True:
            code = f"TT{uuid.uuid4().hex[:16].upper()}"
            if not Ticket.objects.filter(qr_code=code).exists():
                return code
    
    @property
    def buyer_info(self):
        """Return buyer information as a dictionary for API serialization"""
        if self.buyer_name or self.buyer_phone or self.buyer_email:
            return {
                'name': self.buyer_name,
                'phone': self.buyer_phone,
                'email': self.buyer_email
            }
        return None
    
    def activate(self, user, buyer_info=None):
        """Activate the ticket"""
        if self.status != 'unused':
            raise ValueError(f"Cannot activate ticket with status: {self.status}")
        
        self.status = 'activated'
        self.activated_at = timezone.now()
        self.activated_by = user
        
        if buyer_info:
            self.buyer_name = buyer_info.get('name', '')
            self.buyer_phone = buyer_info.get('phone', '')
            self.buyer_email = buyer_info.get('email', '')
            self.notes = buyer_info.get('notes', '')
            if buyer_info.get('ticket_type_id'):
                try:
                    self.ticket_type = TicketType.objects.get(id=buyer_info['ticket_type_id'])
                except TicketType.DoesNotExist:
                    pass
        
        self.save()
    
    def scan(self, user, gate=None):
        """Scan the ticket for entry"""
        if self.status == 'unused':
            raise ValueError("Cannot scan unactivated ticket")
        elif self.status == 'void':
            raise ValueError("Cannot scan voided ticket")
        elif self.status == 'scanned':
            raise ValueError("Ticket already scanned")
        
        self.status = 'scanned'
        self.scanned_at = timezone.now()
        self.scanned_by = user
        self.gate = gate or ''
        self.save()


class ScanLog(BaseModel):
    """Log of all scan attempts for auditing"""
    SCAN_TYPES = [
        ('activate', 'Activate'),
        ('verify', 'Verify'),
    ]
    
    RESULT_TYPES = [
        ('success', 'Success'),
        ('error', 'Error'),
        ('duplicate', 'Duplicate'),
        ('invalid', 'Invalid'),
        ('permission_denied', 'Permission Denied'),
    ]
    
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, null=True, blank=True, related_name='scan_logs')
    qr_code = models.CharField(max_length=255)
    scan_type = models.CharField(max_length=20, choices=SCAN_TYPES)
    result = models.CharField(max_length=20, choices=RESULT_TYPES)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='scan_logs')
    gate = models.CharField(max_length=50, blank=True)
    error_message = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['qr_code']),
            models.Index(fields=['scan_type', 'result']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.scan_type.title()} scan - {self.result} - {self.created_at}"


class BatchExport(BaseModel):
    """Track batch exports for download/print"""
    EXPORT_TYPES = [
        ('pdf', 'PDF'),
        ('csv', 'CSV'),
        ('png', 'PNG Images'),
        ('svg', 'SVG Images'),
    ]
    
    batch = models.ForeignKey(Batch, on_delete=models.CASCADE, related_name='exports')
    export_type = models.CharField(max_length=20, choices=EXPORT_TYPES)
    file_path = models.CharField(max_length=500, blank=True)
    file_size = models.PositiveIntegerField(null=True, blank=True)
    exported_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='batch_exports')
    downloaded_at = models.DateTimeField(null=True, blank=True)
    download_count = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.batch.batch_number} - {self.export_type.upper()} export"


class TemporaryUser(BaseModel):
    """Temporary event-specific user accounts for staff/volunteers"""
    TEMP_USER_ROLES = [
        ('scanner', 'Scanner'),
        ('activator', 'Activator'),
        ('verifier', 'Verifier'),
        ('staff', 'Staff'),
    ]
    
    username = models.CharField(max_length=150, unique=True)
    password_hash = models.CharField(max_length=128)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='temporary_users')
    role = models.CharField(max_length=20, choices=TEMP_USER_ROLES)
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='created_temp_users')
    
    # Permissions
    can_activate = models.BooleanField(default=False)
    can_verify = models.BooleanField(default=False)
    can_scan = models.BooleanField(default=True)
    
    # Tracking
    last_login = models.DateTimeField(null=True, blank=True)
    login_count = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['username', 'event'],
                name='unique_temp_user_username_per_event'
            ),
        ]
    
    def __str__(self):
        return f"{self.username} ({self.event.name})"
    
    def is_expired(self):
        """Check if the temporary user has expired"""
        from django.utils import timezone
        return timezone.now() > self.expires_at
    
    def set_password(self, raw_password):
        """Set password for temporary user"""
        from django.contrib.auth.hashers import make_password
        self.password_hash = make_password(raw_password)
    
    def check_password(self, raw_password):
        """Check password for temporary user"""
        from django.contrib.auth.hashers import check_password
        return check_password(raw_password, self.password_hash)
    
    def record_login(self):
        """Record a login attempt"""
        from django.utils import timezone
        self.last_login = timezone.now()
        self.login_count += 1
        self.save(update_fields=['last_login', 'login_count'])


class EventMembership(BaseModel):
    """Unified event membership model replacing EventManager dual-user system"""
    
    ROLE_CHOICES = [
        ('owner', 'Event Owner'),
        ('manager', 'Event Manager'),
        ('staff', 'Event Staff'),
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='event_memberships')
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='memberships')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='staff')
    permissions = models.JSONField(default=dict, help_text="Granular permissions for this membership")
    invited_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='invitations_sent')
    invited_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True, help_text="When this membership expires (for temporary users)")
    is_active = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ['user', 'event']
        ordering = ['role', 'user__username']
        indexes = [
            models.Index(fields=['event', 'is_active']),
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['expires_at']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.event.name} ({self.get_role_display()})"
    
    def has_permission(self, permission_code):
        """Check if membership has specific permission"""
        if self.role == 'owner':
            return True  # Owners have all permissions
        return self.permissions.get(permission_code, False)
    
    def add_permission(self, permission_code):
        """Add permission to membership"""
        self.permissions[permission_code] = True
        self.save(update_fields=['permissions'])
    
    def remove_permission(self, permission_code):
        """Remove permission from membership"""
        self.permissions.pop(permission_code, None)
        self.save(update_fields=['permissions'])
    
    def is_expired(self):
        """Check if membership has expired"""
        if not self.expires_at:
            return False
        from django.utils import timezone
        return timezone.now() > self.expires_at
    
    @property
    def username(self):
        """Get username for compatibility"""
        return self.user.username
    
    @property
    def email(self):
        """Get email for compatibility"""
        return self.user.email


class BatchMembership(BaseModel):
    """Assign members to specific batches for granular control"""
    batch = models.ForeignKey('Batch', on_delete=models.CASCADE, related_name='batch_memberships')
    membership = models.ForeignKey(EventMembership, on_delete=models.CASCADE, related_name='batch_assignments')
    can_activate = models.BooleanField(default=True)
    can_verify = models.BooleanField(default=True)
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='batch_assignments_made')
    is_active = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ['batch', 'membership']
        ordering = ['batch__batch_number', 'membership__user__username']
    
    def __str__(self):
        return f"{self.membership.user.username} - {self.batch.batch_number}"
