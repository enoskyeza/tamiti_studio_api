
from django.contrib import admin
from .models import SocialPost, PostComment, SocialMetric, SocialPlatformProfile


@admin.register(SocialPost)
class SocialPostAdmin(admin.ModelAdmin):
    list_display = ('title', 'platform', 'status', 'scheduled_for', 'assigned_to', 'reviewer')
    list_filter = ('platform', 'status')
    search_fields = ('title', 'content_text')
    autocomplete_fields = ('assigned_to', 'reviewer')
    ordering = ('-scheduled_for',)


@admin.register(PostComment)
class PostCommentAdmin(admin.ModelAdmin):
    list_display = ('post', 'author', 'created_at')
    search_fields = ('content',)
    autocomplete_fields = ('post', 'author')


@admin.register(SocialMetric)
class SocialMetricAdmin(admin.ModelAdmin):
    list_display = ('post', 'likes', 'comments', 'shares', 'views', 'engagement_score')
    autocomplete_fields = ('post',)


@admin.register(SocialPlatformProfile)
class SocialPlatformProfileAdmin(admin.ModelAdmin):
    list_display = ('platform', 'followers', 'posts_made', 'last_synced')
    list_filter = ('platform',)
