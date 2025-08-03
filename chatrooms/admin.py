from django.contrib import admin
from .models import (
    Channel, ChannelMember, ChannelMessage, MessageFileUpload,
    DirectThread, DirectMessage, DirectMessageFile
)


class MessageFileUploadInline(admin.TabularInline):
    model = MessageFileUpload
    extra = 0
    readonly_fields = ['uploaded_at']


class ChannelMessageAdmin(admin.ModelAdmin):
    list_display = ('channel', 'sender', 'short_content', 'timestamp', 'is_deleted')
    list_filter = ('is_deleted', 'timestamp')
    search_fields = ('content', 'sender__username')
    inlines = [MessageFileUploadInline]

    def short_content(self, obj):
        return obj.content[:40] + ('...' if len(obj.content) > 40 else '')
    short_content.short_description = 'Content'


class ChannelMemberInline(admin.TabularInline):
    model = ChannelMember
    extra = 0


class ChannelAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'is_private', 'created_by')
    list_filter = ('type', 'is_private')
    search_fields = ('name',)
    inlines = [ChannelMemberInline]


class DirectMessageFileInline(admin.TabularInline):
    model = DirectMessageFile
    extra = 0
    readonly_fields = ['uploaded_at']


class DirectMessageAdmin(admin.ModelAdmin):
    list_display = ('thread', 'sender', 'short_content', 'timestamp', 'is_deleted')
    list_filter = ('is_deleted', 'timestamp')
    inlines = [DirectMessageFileInline]

    def short_content(self, obj):
        return obj.content[:40] + ('...' if len(obj.content) > 40 else '')
    short_content.short_description = 'Content'


class DirectThreadAdmin(admin.ModelAdmin):
    list_display = ('user_1', 'user_2', 'created_at')
    search_fields = ('user_1__username', 'user_2__username')


admin.site.register(Channel, ChannelAdmin)
admin.site.register(ChannelMessage, ChannelMessageAdmin)
admin.site.register(ChannelMember)
admin.site.register(DirectThread, DirectThreadAdmin)
admin.site.register(DirectMessage, DirectMessageAdmin)
admin.site.register(MessageFileUpload)
admin.site.register(DirectMessageFile)
