# accounts/admin.py

from django.contrib import admin
from .models import (
    StaffProfile, CustomerProfile,
    Department, Designation, Referral, Branch, StaffRole
)


@admin.register(StaffProfile)
class StaffProfileAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'user', 'role', 'department', 'designation', 'branch', 'is_virtual')
    search_fields = ('name', 'user__first_name', 'user__last_name')
    list_filter = ('branch', 'department', 'designation', 'role__is_virtual')
    autocomplete_fields = ('user', 'assigned_to', 'created_by')

    def is_virtual(self, obj):
        return obj.role.is_virtual if obj.role else False
    is_virtual.boolean = True
    is_virtual.short_description = "Virtual Assistant"

    def display_name(self, obj):
        return obj.name or (obj.user.get_full_name() if obj.user else "[No Name]")
    display_name.short_description = "Name"


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'referred_by')
    list_filter = ('referred_by',)
    search_fields = ('user__username', 'user__email')

@admin.register(Referral)
class ReferralAdmin(admin.ModelAdmin):
    list_display = ('code', 'referrer')
    search_fields = ('code', 'referrer__username')


@admin.register(StaffRole)
class StaffRoleAdmin(admin.ModelAdmin):
    list_display = ('title', 'is_virtual')
    search_fields = ('title',)
    filter_horizontal = ('tags',)

admin.site.register(Department)
admin.site.register(Designation)
admin.site.register(Branch)
