from django.contrib import admin
from field.models import Zone, Lead, Visit, LeadAction


@admin.register(Zone)
class ZoneAdmin(admin.ModelAdmin):
    list_display = ("name", "region", "created_by")
    search_fields = ("name", "region")


class LeadActionInline(admin.TabularInline):
    model = LeadAction
    extra = 0
    readonly_fields = ("type", "date", "outcome", "notes")


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = (
        "business_name", "contact_name", "contact_phone", "assigned_rep",
        "stage", "priority", "zone", "follow_up_date", "lead_score"
    )
    list_filter = ("stage", "priority", "zone", "source")
    search_fields = ("business_name", "contact_name", "contact_phone")
    autocomplete_fields = ("assigned_rep", "zone")
    inlines = [LeadActionInline]
    readonly_fields = ("lead_score",)


@admin.register(Visit)
class VisitAdmin(admin.ModelAdmin):
    list_display = (
        "business_name", "rep", "zone", "location", "visit_outcome",
        "add_as_lead", "linked_lead"
    )
    list_filter = ("visit_outcome", "zone", "rep")
    search_fields = ("business_name", "contact_name", "contact_phone", "location")
    autocomplete_fields = ("rep", "zone", "linked_lead")
