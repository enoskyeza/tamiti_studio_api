from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('actor', 'recipient', 'verb', 'read', 'created_at')
    list_filter = ('read', 'created_at')
    search_fields = ('verb', 'actor__username', 'recipient__username')
