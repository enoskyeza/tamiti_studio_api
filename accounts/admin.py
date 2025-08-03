# accounts/admin.py

from django.contrib import admin
from .models import (
    StaffProfile, CustomerProfile,
    Department, Designation, Referral, Branch, StaffRole
)

@admin.register(StaffProfile)
class StaffProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'department', 'designation', 'branch', 'assigned_to')
    list_filter = ('department', 'designation')
    search_fields = ('user__username', 'user__email')

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
