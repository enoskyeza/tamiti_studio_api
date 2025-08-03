
from django.contrib import admin
from .models import MediaAsset, MediaCategory


@admin.register(MediaAsset)
class MediaAssetAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'asset_type', 'uploaded_by', 'created_at')
    search_fields = ('title', 'caption', 'alt_text', 'description')
    list_filter = ('asset_type', 'category')
    readonly_fields = ('created_at', 'updated_at')
    autocomplete_fields = ('category', 'uploaded_by')


@admin.register(MediaCategory)
class MediaCategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)
