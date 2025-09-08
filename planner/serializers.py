from rest_framework import serializers

from planner.models import (
    BreakPolicy, AvailabilityTemplate, CalendarEvent, TimeBlock,
    DailyReview, WorkGoal, ProductivityInsight
)


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
    task_title = serializers.CharField(read_only=True, source='task.title')
    task_priority = serializers.CharField(read_only=True, source='task.priority')

    class Meta:
        model = TimeBlock
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')


class DailyReviewSerializer(serializers.ModelSerializer):
    """Serializer for daily productivity reviews"""
    
    class Meta:
        model = DailyReview
        fields = (
            'id', 'date', 'summary', 'mood', 'highlights', 'lessons', 'tomorrow_top3',
            'tasks_planned', 'tasks_completed', 'completion_rate', 'focus_time_minutes',
            'break_time_minutes', 'productivity_score', 'current_streak', 'created_at', 'updated_at'
        )
        read_only_fields = (
            'tasks_planned', 'tasks_completed', 'completion_rate', 'focus_time_minutes',
            'break_time_minutes', 'productivity_score', 'current_streak', 'created_at', 'updated_at'
        )

    def validate_tomorrow_top3(self, value):
        """Ensure tomorrow_top3 is a list with max 3 items"""
        if not isinstance(value, list):
            raise serializers.ValidationError("tomorrow_top3 must be a list")
        if len(value) > 3:
            raise serializers.ValidationError("tomorrow_top3 can have maximum 3 items")
        return value


class WorkGoalSerializer(serializers.ModelSerializer):
    """Serializer for work goals"""
    progress_percentage = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    total_tasks = serializers.IntegerField(read_only=True)
    completed_tasks = serializers.IntegerField(read_only=True)
    owner_user_email = serializers.CharField(read_only=True, source='owner_user.email')
    owner_team_name = serializers.CharField(read_only=True, source='owner_team.name')
    project_name = serializers.CharField(read_only=True, source='project.name')
    
    class Meta:
        model = WorkGoal
        fields = (
            'id', 'name', 'description', 'target_date', 'owner_user', 'owner_team', 'project',
            'tags', 'is_active', 'progress_percentage', 'total_tasks', 'completed_tasks',
            'owner_user_email', 'owner_team_name', 'project_name', 'created_at', 'updated_at'
        )
        read_only_fields = (
            'progress_percentage', 'total_tasks', 'completed_tasks', 'created_at', 'updated_at'
        )

    def validate_tags(self, value):
        """Ensure tags is a list of strings"""
        if not isinstance(value, list):
            raise serializers.ValidationError("tags must be a list")
        for tag in value:
            if not isinstance(tag, str):
                raise serializers.ValidationError("All tags must be strings")
        return value


class ProductivityInsightSerializer(serializers.ModelSerializer):
    """Serializer for productivity insights"""
    
    class Meta:
        model = ProductivityInsight
        fields = (
            'id', 'insight_type', 'data', 'confidence_score', 'sample_size',
            'valid_from', 'valid_until', 'is_active', 'created_at', 'updated_at'
        )
        read_only_fields = ('created_at', 'updated_at')


class ProductivityStatsSerializer(serializers.Serializer):
    """Serializer for productivity statistics response"""
    avg_productivity_score = serializers.DecimalField(max_digits=5, decimal_places=2)
    avg_completion_rate = serializers.DecimalField(max_digits=5, decimal_places=2)
    current_streak = serializers.IntegerField()
    total_focus_hours = serializers.DecimalField(max_digits=6, decimal_places=1)
    trend = serializers.ChoiceField(choices=['improving', 'stable', 'declining', 'no_data'])
    total_days = serializers.IntegerField()


class SchedulePreviewSerializer(serializers.Serializer):
    """Serializer for schedule preview requests"""
    scope = serializers.ChoiceField(choices=['day', 'week'], default='day')
    date = serializers.DateField()
    smart = serializers.BooleanField(default=True)


class RescheduleRequestSerializer(serializers.Serializer):
    """Serializer for rescheduling requests"""
    from_date = serializers.DateField()
    to_date = serializers.DateField(required=False)


class BulkRescheduleSerializer(serializers.Serializer):
    """Serializer for bulk task rescheduling"""
    task_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1,
        max_length=50  # Reasonable limit
    )
    target_date = serializers.DateField()

