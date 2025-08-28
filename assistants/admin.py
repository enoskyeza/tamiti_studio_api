from django.contrib import admin
from .models import VACommand, DefaultResponse, AssistantLog


class VACommandInline(admin.TabularInline):
    model = VACommand
    extra = 1


class DefaultResponseInline(admin.TabularInline):
    model = DefaultResponse
    extra = 1


@admin.register(VACommand)
class VACommandAdmin(admin.ModelAdmin):
    list_display = ('assistant', 'trigger_text', 'match_type', 'response_mode')
    list_filter = ('match_type', 'response_mode', 'assistant')
    search_fields = ('trigger_text', 'assistant__title')


@admin.register(DefaultResponse)
class DefaultResponseAdmin(admin.ModelAdmin):
    list_display = ('assistant', 'condition', 'fallback_text')
    search_fields = ('assistant__title', 'condition')


@admin.register(AssistantLog)
class AssistantLogAdmin(admin.ModelAdmin):
    list_display = ('assistant', 'user', 'timestamp', 'used_gpt')
    readonly_fields = ('timestamp', 'user', 'assistant', 'message_sent', 'response_text')
    search_fields = ('assistant__title', 'user__username')
