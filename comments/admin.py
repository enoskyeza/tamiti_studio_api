from django.contrib import admin
from .models import Comment


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'author', 'content_type', 'object_id', 'parent', 'is_internal', 'created_at'
    )
    list_filter = ('is_internal', 'content_type')
    search_fields = ('content',)
    autocomplete_fields = ('author', 'parent')

