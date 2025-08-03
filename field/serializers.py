from rest_framework import serializers
from field.models import Zone, Lead, Visit, LeadAction


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

    class Meta:
        model = Lead
        fields = '__all__'
        read_only_fields = ('lead_score',)


class VisitSerializer(serializers.ModelSerializer):
    linked_lead = LeadSerializer(read_only=True)

    class Meta:
        model = Visit
        fields = '__all__'
