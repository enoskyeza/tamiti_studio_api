from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count
from .models import Event, TicketType, Batch, Ticket, ScanLog, BatchExport


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
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


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
