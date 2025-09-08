from rest_framework import serializers

from planner.models import BreakPolicy, AvailabilityTemplate, CalendarEvent, TimeBlock


class BreakPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = BreakPolicy
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')


class AvailabilityTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = AvailabilityTemplate
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')


class CalendarEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = CalendarEvent
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')


class TimeBlockSerializer(serializers.ModelSerializer):
    duration_minutes = serializers.IntegerField(read_only=True, source='duration_minutes')

    class Meta:
        model = TimeBlock
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')

