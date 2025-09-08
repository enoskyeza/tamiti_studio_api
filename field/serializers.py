from rest_framework import serializers
from field.models import Zone, Lead, Visit, LeadAction
from common.enums import LeadStatus
from users.models import User


class ZoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = Zone
        fields = '__all__'


class LeadActionSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeadAction
        fields = '__all__'
        read_only_fields = ('created_by',)


class LeadSerializer(serializers.ModelSerializer):
    actions = LeadActionSerializer(many=True, read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Lead
        fields = '__all__'
        read_only_fields = ('lead_score',)

    def validate_status(self, value):
        # Accept either enum value (e.g., 'closed_subscribed') or human label (e.g., 'Closed – Subscribed')
        if value in dict(LeadStatus.choices()):
            return value
        # Try to map human label back to value
        label_to_value = {label: val for val, label in LeadStatus.choices()}
        return label_to_value.get(value, value)


# --- Read serializers to expose human-friendly fields ---

class UserSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username", "first_name", "last_name")


class LeadActionReadSerializer(serializers.ModelSerializer):
    created_by = UserSummarySerializer(read_only=True)

    class Meta:
        model = LeadAction
        fields = '__all__'


class LeadReadSerializer(LeadSerializer):
    assigned_rep = UserSummarySerializer(read_only=True)
    zone = serializers.CharField(source='zone.name', read_only=True)
    actions = LeadActionReadSerializer(many=True, read_only=True)

    class Meta(LeadSerializer.Meta):
        fields = '__all__'


class VisitSerializer(serializers.ModelSerializer):
    linked_lead = LeadSerializer(read_only=True)

    class Meta:
        model = Visit
        fields = '__all__'


class VisitReadSerializer(serializers.ModelSerializer):
    rep = UserSummarySerializer(read_only=True)
    zone = serializers.CharField(source='zone.name', read_only=True)
    linked_lead = LeadReadSerializer(read_only=True)

    class Meta:
        model = Visit
        fields = '__all__'


class VisitSerializer(serializers.ModelSerializer):
    linked_lead = LeadSerializer(read_only=True)

    class Meta:
        model = Visit
        fields = '__all__'
