from django.contrib import admin
from .models import DashboardWidget

@admin.register(DashboardWidget)
class DashboardWidgetAdmin(admin.ModelAdmin):
    list_display = ["user", "name", "position", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["name", "user__email"]