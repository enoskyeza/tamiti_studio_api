from django.contrib import admin
from django import forms
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count
from .models import (
    Event, EventManager, BatchManager,
    TicketType, Batch, Ticket, ScanLog, BatchExport,
)


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
    
    class EventManagerInlineForm(forms.ModelForm):
        permissions = forms.MultipleChoiceField(
            choices=EventManager.PERMISSION_CHOICES,
            required=False,
            widget=forms.CheckboxSelectMultiple,
            help_text="Select permissions for this manager",
        )

        class Meta:
            model = EventManager
            fields = ['user', 'role', 'permissions', 'is_active']

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            # Ensure JSON list -> form list
            if self.instance and self.instance.pk and isinstance(self.instance.permissions, list):
                self.initial['permissions'] = self.instance.permissions

        def clean_permissions(self):
            data = self.cleaned_data.get('permissions') or []
            # store codes as list
            return list(data)

    class EventManagerInline(admin.StackedInline):
        model = EventManager
        extra = 0
        form = EventAdmin.EventManagerInlineForm
        autocomplete_fields = ['user']
        fields = ('user', 'role', 'permissions', 'is_active')
        show_change_link = True

    inlines = [EventManagerInline]
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for inst in instances:
            if isinstance(inst, EventManager) and not inst.assigned_by_id:
                inst.assigned_by = request.user
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
    class BatchManagerInline(admin.TabularInline):
        model = BatchManager
        extra = 0
        autocomplete_fields = ['manager']
        fields = ['manager', 'can_activate', 'can_verify']
        show_change_link = True

    inlines = [BatchManagerInline, TicketInline]
    
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
            if isinstance(inst, BatchManager) and not inst.assigned_by_id:
                inst.assigned_by = request.user
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


# ============ EventManager admin ============

class EventManagerAdminForm(forms.ModelForm):
    permissions = forms.MultipleChoiceField(
        choices=EventManager.PERMISSION_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text="Select permissions for this manager",
    )

    class Meta:
        model = EventManager
        fields = ['event', 'user', 'role', 'permissions', 'is_active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and isinstance(self.instance.permissions, list):
            self.initial['permissions'] = self.instance.permissions

    def clean_permissions(self):
        return list(self.cleaned_data.get('permissions') or [])


@admin.register(EventManager)
class EventManagerAdmin(admin.ModelAdmin):
    form = EventManagerAdminForm
    list_display = [
        'event', 'user', 'role', 'permissions_short', 'is_active', 'assigned_by', 'created_at'
    ]
    list_filter = ['role', 'is_active', 'event', 'created_at']
    search_fields = ['event__name', 'user__username', 'user__email']
    autocomplete_fields = ['event', 'user', 'assigned_by']
    readonly_fields = ['created_at', 'updated_at']
    list_select_related = ['event', 'user', 'assigned_by']

    actions = ['activate_managers', 'deactivate_managers', 'grant_all_permissions', 'revoke_all_permissions']

    def permissions_short(self, obj):
        if not obj.permissions:
            return '-'
        return ', '.join(obj.permissions)[:80] + ('…' if len(', '.join(obj.permissions)) > 80 else '')
    permissions_short.short_description = 'Permissions'

    def save_model(self, request, obj, form, change):
        if not change and not obj.assigned_by_id:
            obj.assigned_by = request.user
        super().save_model(request, obj, form, change)

    def activate_managers(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"Activated {updated} manager(s)")
    activate_managers.short_description = "Activate selected managers"

    def deactivate_managers(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"Deactivated {updated} manager(s)")
    deactivate_managers.short_description = "Deactivate selected managers"

    def grant_all_permissions(self, request, queryset):
        all_codes = [c[0] for c in EventManager.PERMISSION_CHOICES]
        for m in queryset:
            m.permissions = list(set((m.permissions or []) + all_codes))
            m.save()
        self.message_user(request, "Granted all permissions to selected managers")
    grant_all_permissions.short_description = "Grant all permissions"

    def revoke_all_permissions(self, request, queryset):
        for m in queryset:
            m.permissions = []
            m.save()
        self.message_user(request, "Revoked all permissions from selected managers")
    revoke_all_permissions.short_description = "Revoke all permissions"


# ============ BatchManager admin ============

@admin.register(BatchManager)
class BatchManagerAdmin(admin.ModelAdmin):
    list_display = ['batch', 'event_name', 'manager_user', 'can_activate', 'can_verify', 'assigned_by', 'created_at']
    list_filter = ['can_activate', 'can_verify', 'batch__event', 'created_at']
    search_fields = ['batch__batch_number', 'batch__event__name', 'manager__user__username', 'manager__user__email']
    autocomplete_fields = ['batch', 'manager', 'assigned_by']
    list_select_related = ['batch__event', 'manager__user', 'assigned_by']
    readonly_fields = ['created_at', 'updated_at']

    actions = ['enable_activation', 'disable_activation', 'enable_verification', 'disable_verification']

    def event_name(self, obj):
        return obj.batch.event.name
    event_name.short_description = 'Event'

    def manager_user(self, obj):
        return obj.manager.user
    manager_user.short_description = 'Manager User'

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
