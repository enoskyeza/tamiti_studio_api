from django.contrib import admin
from django import forms
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count
from .models import (
    Event, TicketType, Batch, Ticket, ScanLog, BatchExport, TemporaryUser,
    EventMembership, BatchMembership,
)

# ===== Forms and Inlines (top-level to avoid NameError) =====



class TemporaryUserInline(admin.TabularInline):
    model = TemporaryUser
    extra = 0
    fields = ['username', 'role', 'is_active', 'expires_at', 'can_activate', 'can_verify']
    readonly_fields = ['last_login', 'login_count']
    show_change_link = True


class EventMembershipInline(admin.TabularInline):
    """Inline for managing event memberships within Event admin"""
    model = EventMembership
    extra = 0
    autocomplete_fields = ['user', 'invited_by']
    fields = ['user', 'role', 'permissions_display', 'is_active', 'expires_at']
    readonly_fields = ['permissions_display', 'invited_by', 'created_at']
    show_change_link = True
    
    def permissions_display(self, obj):
        if not obj.permissions:
            return '-'
        perms = obj.permissions
        if isinstance(perms, dict):
            return ', '.join([f"{k}: {v}" for k, v in perms.items() if v])
        return str(perms)
    permissions_display.short_description = 'Permissions'


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ['name', 'date', 'venue', 'status', 'created_by', 'created_at']
    list_filter = ['status', 'date', 'created_at']
    search_fields = ['name', 'venue']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        (None, {
            'fields': ('name', 'description', 'date', 'venue', 'status')
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [EventMembershipInline]  # Updated to use new unified membership system
    # Legacy inlines removed: EventManagerInline, TemporaryUserInline
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for inst in instances:
            if isinstance(inst, EventMembership) and not inst.invited_by_id:
                inst.invited_by = request.user
            inst.save()
        formset.save_m2m()


class TicketTypeInline(admin.TabularInline):
    model = TicketType
    extra = 1
    fields = ['name', 'price', 'description', 'max_quantity', 'is_active']


@admin.register(TicketType)
class TicketTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'event', 'price', 'max_quantity', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at', 'event']
    search_fields = ['name', 'event__name']
    readonly_fields = ['created_at']


class TicketInline(admin.TabularInline):
    model = Ticket
    extra = 0
    readonly_fields = ['short_code', 'qr_code', 'status', 'activated_at', 'scanned_at']
    fields = ['short_code', 'qr_code', 'status', 'buyer_name', 'buyer_phone']
    can_delete = False
    max_num = 10  # Limit display for performance


@admin.register(Batch)
class BatchAdmin(admin.ModelAdmin):
    list_display = [
        'batch_number', 'event', 'quantity', 'status', 'activated_count_display',
        'scanned_count_display', 'created_by', 'created_at'
    ]
    list_filter = ['status', 'created_at', 'event']
    search_fields = ['batch_number', 'event__name']
    readonly_fields = [
        'batch_number', 'created_at', 'activated_count_display',
        'scanned_count_display', 'unused_count_display', 'voided_count_display'
    ]
    inlines = [TicketInline]
    
    fieldsets = (
        (None, {
            'fields': ('event', 'quantity', 'status')
        }),
        ('Layout Configuration', {
            'fields': ('layout_columns', 'layout_rows', 'qr_size', 'include_short_code')
        }),
        ('Void Information', {
            'fields': ('voided_at', 'voided_by', 'void_reason'),
            'classes': ('collapse',)
        }),
        ('Statistics', {
            'fields': (
                'activated_count_display', 'scanned_count_display',
                'unused_count_display', 'voided_count_display'
            ),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('batch_number', 'created_by', 'created_at'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for inst in instances:
            inst.save()
        formset.save_m2m()
    
    def activated_count_display(self, obj):
        return obj.activated_count
    activated_count_display.short_description = 'Activated'
    
    def scanned_count_display(self, obj):
        return obj.scanned_count
    scanned_count_display.short_description = 'Scanned'
    
    def unused_count_display(self, obj):
        return obj.unused_count
    unused_count_display.short_description = 'Unused'
    
    def voided_count_display(self, obj):
        return obj.voided_count
    voided_count_display.short_description = 'Voided'


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = [
        'short_code', 'batch', 'status', 'buyer_name', 'buyer_phone',
        'activated_at', 'scanned_at'
    ]
    list_filter = ['status', 'batch__event', 'activated_at', 'scanned_at']
    search_fields = ['short_code', 'qr_code', 'buyer_name', 'buyer_phone', 'buyer_email']
    readonly_fields = [
        'short_code', 'qr_code', 'created_at', 'activated_at', 'scanned_at'
    ]
    
    fieldsets = (
        (None, {
            'fields': ('batch', 'short_code', 'qr_code', 'status')
        }),
        ('Buyer Information', {
            'fields': ('buyer_name', 'buyer_phone', 'buyer_email', 'ticket_type', 'notes')
        }),
        ('Activation', {
            'fields': ('activated_at', 'activated_by'),
            'classes': ('collapse',)
        }),
        ('Scanning', {
            'fields': ('scanned_at', 'scanned_by', 'gate'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'batch__event', 'activated_by', 'scanned_by', 'ticket_type'
        )


@admin.register(ScanLog)
class ScanLogAdmin(admin.ModelAdmin):
    list_display = [
        'created_at', 'scan_type', 'result', 'ticket_code', 'user', 'gate'
    ]
    list_filter = ['scan_type', 'result', 'created_at']
    search_fields = ['qr_code', 'ticket__short_code', 'user__username', 'gate']
    readonly_fields = [
        'ticket', 'qr_code', 'scan_type', 'result', 'user', 'gate',
        'error_message', 'ip_address', 'user_agent', 'created_at'
    ]
    
    fieldsets = (
        (None, {
            'fields': ('ticket', 'qr_code', 'scan_type', 'result', 'user', 'gate')
        }),
        ('Error Details', {
            'fields': ('error_message',),
            'classes': ('collapse',)
        }),
        ('Technical Details', {
            'fields': ('ip_address', 'user_agent'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def ticket_code(self, obj):
        if obj.ticket:
            return obj.ticket.short_code
        return '-'
    ticket_code.short_description = 'Ticket Code'
    
    def has_add_permission(self, request):
        return False  # Scan logs are created automatically
    
    def has_change_permission(self, request, obj=None):
        return False  # Scan logs should not be modified
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser  # Only superusers can delete logs


@admin.register(BatchExport)
class BatchExportAdmin(admin.ModelAdmin):
    list_display = [
        'batch', 'export_type', 'exported_by', 'created_at',
        'download_count', 'file_size_display'
    ]
    list_filter = ['export_type', 'created_at']
    search_fields = ['batch__batch_number', 'exported_by__username']
    readonly_fields = [
        'batch', 'export_type', 'file_path', 'file_size', 'exported_by',
        'created_at', 'downloaded_at', 'download_count'
    ]
    
    def file_size_display(self, obj):
        if obj.file_size:
            if obj.file_size < 1024:
                return f"{obj.file_size} B"
            elif obj.file_size < 1024 * 1024:
                return f"{obj.file_size / 1024:.1f} KB"
            else:
                return f"{obj.file_size / (1024 * 1024):.1f} MB"
        return '-'
    file_size_display.short_description = 'File Size'
    
    def has_add_permission(self, request):
        return False  # Exports are created through API
    
    def has_change_permission(self, request, obj=None):
        return False  # Exports should not be modified


# ============ NEW UNIFIED MEMBERSHIP SYSTEM ADMIN ============

@admin.register(EventMembership)
class EventMembershipAdmin(admin.ModelAdmin):
    """Admin interface for the new unified EventMembership model"""
    list_display = [
        'event', 'user', 'role', 'permissions_summary', 'is_active', 
        'expires_at', 'invited_by', 'created_at'
    ]
    list_filter = ['role', 'is_active', 'event', 'created_at', 'expires_at']
    search_fields = ['event__name', 'user__username', 'user__email', 'user__first_name', 'user__last_name']
    autocomplete_fields = ['event', 'user', 'invited_by']
    readonly_fields = ['created_at', 'updated_at']
    list_select_related = ['event', 'user', 'invited_by']
    
    actions = ['activate_memberships', 'deactivate_memberships', 'extend_expiry']
    
    fieldsets = (
        (None, {
            'fields': ('event', 'user', 'role', 'is_active')
        }),
        ('Permissions', {
            'fields': ('permissions',),
            'description': 'JSON object with permission scopes and values'
        }),
        ('Expiry', {
            'fields': ('expires_at',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('invited_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def permissions_summary(self, obj):
        if not obj.permissions:
            return '-'
        perms = obj.permissions
        if isinstance(perms, dict):
            active_perms = [k for k, v in perms.items() if v]
            return ', '.join(active_perms[:3]) + ('...' if len(active_perms) > 3 else '')
        return str(perms)[:50] + ('...' if len(str(perms)) > 50 else '')
    permissions_summary.short_description = 'Permissions'
    
    def save_model(self, request, obj, form, change):
        if not change and not obj.invited_by_id:
            obj.invited_by = request.user
        super().save_model(request, obj, form, change)
    
    def activate_memberships(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"Activated {updated} membership(s)")
    activate_memberships.short_description = "Activate selected memberships"
    
    def deactivate_memberships(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"Deactivated {updated} membership(s)")
    deactivate_memberships.short_description = "Deactivate selected memberships"
    
    def extend_expiry(self, request, queryset):
        from django.utils import timezone
        from datetime import timedelta
        
        new_expiry = timezone.now() + timedelta(days=30)
        updated = queryset.update(expires_at=new_expiry)
        self.message_user(request, f"Extended expiry for {updated} membership(s) by 30 days")
    extend_expiry.short_description = "Extend expiry by 30 days"


@admin.register(BatchMembership)
class BatchMembershipAdmin(admin.ModelAdmin):
    """Admin interface for the new unified BatchMembership model"""
    list_display = [
        'batch', 'event_name', 'user_name', 'can_activate', 'can_verify', 
        'is_active', 'assigned_by', 'created_at'
    ]
    list_filter = ['can_activate', 'can_verify', 'is_active', 'batch__event', 'created_at']
    search_fields = [
        'batch__batch_number', 'batch__event__name', 
        'membership__user__username', 'membership__user__email',
        'membership__user__first_name', 'membership__user__last_name'
    ]
    autocomplete_fields = ['batch', 'membership', 'assigned_by']
    readonly_fields = ['created_at', 'updated_at']
    list_select_related = ['batch__event', 'membership__user', 'assigned_by']
    
    actions = [
        'enable_activation', 'disable_activation', 
        'enable_verification', 'disable_verification',
        'activate_memberships', 'deactivate_memberships'
    ]
    
    fieldsets = (
        (None, {
            'fields': ('batch', 'membership', 'is_active')
        }),
        ('Permissions', {
            'fields': ('can_activate', 'can_verify')
        }),
        ('Metadata', {
            'fields': ('assigned_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def event_name(self, obj):
        return obj.batch.event.name
    event_name.short_description = 'Event'
    
    def user_name(self, obj):
        user = obj.membership.user
        return f"{user.get_full_name() or user.username}"
    user_name.short_description = 'User'
    
    def save_model(self, request, obj, form, change):
        if not change and not obj.assigned_by_id:
            obj.assigned_by = request.user
        super().save_model(request, obj, form, change)
    
    def enable_activation(self, request, queryset):
        updated = queryset.update(can_activate=True)
        self.message_user(request, f"Enabled activation for {updated} assignment(s)")
    enable_activation.short_description = "Enable activation"
    
    def disable_activation(self, request, queryset):
        updated = queryset.update(can_activate=False)
        self.message_user(request, f"Disabled activation for {updated} assignment(s)")
    disable_activation.short_description = "Disable activation"
    
    def enable_verification(self, request, queryset):
        updated = queryset.update(can_verify=True)
        self.message_user(request, f"Enabled verification for {updated} assignment(s)")
    enable_verification.short_description = "Enable verification"
    
    def disable_verification(self, request, queryset):
        updated = queryset.update(can_verify=False)
        self.message_user(request, f"Disabled verification for {updated} assignment(s)")
    disable_verification.short_description = "Disable verification"
    
    def activate_memberships(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"Activated {updated} batch membership(s)")
    activate_memberships.short_description = "Activate selected memberships"
    
    def deactivate_memberships(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"Deactivated {updated} batch membership(s)")
    deactivate_memberships.short_description = "Deactivate selected memberships"
    
    class Meta:
        model = TemporaryUser
        fields = [
            'username', 'password', 'confirm_password', 'event', 'role',
            'is_active', 'expires_at', 'can_activate', 'can_verify', 'can_scan'
        ]
    
    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')
        
        if password and password != confirm_password:
            raise forms.ValidationError("Passwords don't match")
        
        return cleaned_data
    
    def save(self, commit=True):
        temp_user = super().save(commit=False)
        password = self.cleaned_data.get('password')
        
        if password:
            temp_user.set_password(password)
        
        if commit:
            temp_user.save()
        return temp_user


@admin.register(TemporaryUser)
class TemporaryUserAdmin(admin.ModelAdmin):
    form = TemporaryUserAdminForm
    list_display = [
        'username', 'event', 'role', 'is_active', 'expires_at', 
        'is_expired_display', 'login_count', 'last_login', 'created_by'
    ]
    list_filter = ['role', 'is_active', 'event', 'expires_at', 'created_at']
    search_fields = ['username', 'event__name', 'created_by__username']
    autocomplete_fields = ['event', 'created_by']
    readonly_fields = ['created_at', 'updated_at', 'last_login', 'login_count']
    list_select_related = ['event', 'created_by']
    
    actions = [
        'activate_users', 'deactivate_users', 'extend_expiry', 
        'enable_all_permissions', 'disable_all_permissions'
    ]
    
    fieldsets = (
        (None, {
            'fields': ('username', 'password', 'confirm_password', 'event', 'role', 'is_active')
        }),
        ('Permissions', {
            'fields': ('can_activate', 'can_verify', 'can_scan')
        }),
        ('Expiry', {
            'fields': ('expires_at',)
        }),
        ('Statistics', {
            'fields': ('last_login', 'login_count'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def is_expired_display(self, obj):
        if obj.is_expired():
            return format_html('<span style="color: red;">Expired</span>')
        return format_html('<span style="color: green;">Active</span>')
    is_expired_display.short_description = 'Status'
    
    def save_model(self, request, obj, form, change):
        if not change and not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    def activate_users(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"Activated {updated} temporary user(s)")
    activate_users.short_description = "Activate selected users"
    
    def deactivate_users(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"Deactivated {updated} temporary user(s)")
    deactivate_users.short_description = "Deactivate selected users"
    
    def extend_expiry(self, request, queryset):
        from django.utils import timezone
        from datetime import timedelta
        
        new_expiry = timezone.now() + timedelta(days=30)
        updated = queryset.update(expires_at=new_expiry)
        self.message_user(request, f"Extended expiry for {updated} user(s) by 30 days")
    extend_expiry.short_description = "Extend expiry by 30 days"
    
    def enable_all_permissions(self, request, queryset):
        updated = queryset.update(can_activate=True, can_verify=True, can_scan=True)
        self.message_user(request, f"Enabled all permissions for {updated} user(s)")
    enable_all_permissions.short_description = "Enable all permissions"
    
    def disable_all_permissions(self, request, queryset):
        updated = queryset.update(can_activate=False, can_verify=False, can_scan=False)
        self.message_user(request, f"Disabled all permissions for {updated} user(s)")
    disable_all_permissions.short_description = "Disable all permissions"


# ============ NEW UNIFIED MEMBERSHIP SYSTEM ADMIN ============
# (EventMembershipInline moved above EventAdmin class to fix import order)


@admin.register(EventMembership)
class EventMembershipAdmin(admin.ModelAdmin):
    """Admin interface for the new unified EventMembership model"""
    list_display = [
        'event', 'user', 'role', 'permissions_summary', 'is_active', 
        'expires_at', 'invited_by', 'created_at'
    ]
    list_filter = ['role', 'is_active', 'event', 'created_at', 'expires_at']
    search_fields = ['event__name', 'user__username', 'user__email', 'user__first_name', 'user__last_name']
    autocomplete_fields = ['event', 'user', 'invited_by']
    readonly_fields = ['created_at', 'updated_at']
    list_select_related = ['event', 'user', 'invited_by']
    
    actions = ['activate_memberships', 'deactivate_memberships', 'extend_expiry']
    
    fieldsets = (
        (None, {
            'fields': ('event', 'user', 'role', 'is_active')
        }),
        ('Permissions', {
            'fields': ('permissions',),
            'description': 'JSON object with permission scopes and values'
        }),
        ('Expiry', {
            'fields': ('expires_at',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('invited_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def permissions_summary(self, obj):
        if not obj.permissions:
            return '-'
        perms = obj.permissions
        if isinstance(perms, dict):
            active_perms = [k for k, v in perms.items() if v]
            return ', '.join(active_perms[:3]) + ('...' if len(active_perms) > 3 else '')
        return str(perms)[:50] + ('...' if len(str(perms)) > 50 else '')
    permissions_summary.short_description = 'Permissions'
    
    def save_model(self, request, obj, form, change):
        if not change and not obj.invited_by_id:
            obj.invited_by = request.user
        super().save_model(request, obj, form, change)
    
    def activate_memberships(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"Activated {updated} membership(s)")
    activate_memberships.short_description = "Activate selected memberships"
    
    def deactivate_memberships(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"Deactivated {updated} membership(s)")
    deactivate_memberships.short_description = "Deactivate selected memberships"
    
    def extend_expiry(self, request, queryset):
        from django.utils import timezone
        from datetime import timedelta
        
        new_expiry = timezone.now() + timedelta(days=30)
        updated = queryset.update(expires_at=new_expiry)
        self.message_user(request, f"Extended expiry for {updated} membership(s) by 30 days")
    extend_expiry.short_description = "Extend expiry by 30 days"


@admin.register(BatchMembership)
class BatchMembershipAdmin(admin.ModelAdmin):
    """Admin interface for the new unified BatchMembership model"""
    list_display = [
        'batch', 'event_name', 'user_name', 'can_activate', 'can_verify', 
        'is_active', 'assigned_by', 'created_at'
    ]
    list_filter = ['can_activate', 'can_verify', 'is_active', 'batch__event', 'created_at']
    search_fields = [
        'batch__batch_number', 'batch__event__name', 
        'membership__user__username', 'membership__user__email',
        'membership__user__first_name', 'membership__user__last_name'
    ]
    autocomplete_fields = ['batch', 'membership', 'assigned_by']
    readonly_fields = ['created_at', 'updated_at']
    list_select_related = ['batch__event', 'membership__user', 'assigned_by']
    
    actions = [
        'enable_activation', 'disable_activation', 
        'enable_verification', 'disable_verification',
        'activate_memberships', 'deactivate_memberships'
    ]
    
    fieldsets = (
        (None, {
            'fields': ('batch', 'membership', 'is_active')
        }),
        ('Permissions', {
            'fields': ('can_activate', 'can_verify')
        }),
        ('Metadata', {
            'fields': ('assigned_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def event_name(self, obj):
        return obj.batch.event.name
    event_name.short_description = 'Event'
    
    def user_name(self, obj):
        user = obj.membership.user
        return f"{user.get_full_name() or user.username}"
    user_name.short_description = 'User'
    
    def save_model(self, request, obj, form, change):
        if not change and not obj.assigned_by_id:
            obj.assigned_by = request.user
        super().save_model(request, obj, form, change)
    
    def enable_activation(self, request, queryset):
        updated = queryset.update(can_activate=True)
        self.message_user(request, f"Enabled activation for {updated} assignment(s)")
    enable_activation.short_description = "Enable activation"
    
    def disable_activation(self, request, queryset):
        updated = queryset.update(can_activate=False)
        self.message_user(request, f"Disabled activation for {updated} assignment(s)")
    disable_activation.short_description = "Disable activation"
    
    def enable_verification(self, request, queryset):
        updated = queryset.update(can_verify=True)
        self.message_user(request, f"Enabled verification for {updated} assignment(s)")
    enable_verification.short_description = "Enable verification"
    
    def disable_verification(self, request, queryset):
        updated = queryset.update(can_verify=False)
        self.message_user(request, f"Disabled verification for {updated} assignment(s)")
    disable_verification.short_description = "Disable verification"
    
    def activate_memberships(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"Activated {updated} batch membership(s)")
    activate_memberships.short_description = "Activate selected memberships"
    
    def deactivate_memberships(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"Deactivated {updated} batch membership(s)")
    deactivate_memberships.short_description = "Deactivate selected memberships"


# ============ LEGACY MODEL ADMIN (DEPRECATED) ============

# Mark legacy admin classes as deprecated by adding warnings
EventManagerAdmin.list_display_links = None  # Make read-only
EventManagerAdmin.actions = []  # Remove actions

BatchManagerAdmin.list_display_links = None  # Make read-only  
BatchManagerAdmin.actions = []  # Remove actions

TemporaryUserAdmin.list_display_links = None  # Make read-only
TemporaryUserAdmin.actions = []  # Remove actions
