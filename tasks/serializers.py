from rest_framework import serializers
from tasks.models import Task, TaskGroup
from accounts.models import Department
from taggit.serializers import TaggitSerializer, TagListSerializerField


class TaskGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskGroup
        fields = '__all__'


class TaskSerializer(serializers.ModelSerializer):
    is_overdue = serializers.ReadOnlyField()
    project_name = serializers.CharField(source='project.name', read_only=True)
    assigned_to_email = serializers.EmailField(source='assigned_to.email', read_only=True)
    assigned_team_name = serializers.CharField(source='assigned_team.name', read_only=True)

    class Meta:
        model = Task
        fields = (
            'id', 'project', 'project_name', 'title', 'description', 'status',
            'priority', 'due_date', 'start_at', 'earliest_start_at', 'latest_finish_at',
            'snoozed_until', 'backlog_date', 'estimated_minutes', 'estimated_hours', 'actual_hours',
            'assigned_to', 'assigned_to_email', 'assigned_team', 'assigned_team_name',
            'dependencies', 'milestone', 'origin_app', 'created_by', 'notes',
            'position', 'is_completed', 'completed_at', 'is_hard_due', 'parent',
            'context_energy', 'context_location', 'recurrence_rule',
            'created_at', 'updated_at', 'is_overdue'
        )
        read_only_fields = ('created_at', 'updated_at', 'completed_at')


class TaskCreateSerializer(TaggitSerializer, serializers.ModelSerializer):
    dependencies = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Task.objects.all(), required=False
    )
    tags = TagListSerializerField(required=False)

    class Meta:
        model = Task
        fields = (
            'project', 'title', 'description', 'priority', 'due_date', 'start_at',
            'earliest_start_at', 'latest_finish_at', 'snoozed_until', 'backlog_date',
            'estimated_minutes', 'estimated_hours', 'assigned_to', 'assigned_team', 'notes', 'origin_app',
            'milestone', 'dependencies', 'tags', 'is_hard_due', 'parent', 'context_energy', 'context_location',
            'recurrence_rule'
        )


class TaskUpdateSerializer(TaggitSerializer, serializers.ModelSerializer):
    dependencies = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Task.objects.all(), required=False
    )
    tags = TagListSerializerField(required=False)

    class Meta:
        model = Task
        fields = (
            'title', 'description', 'priority', 'status', 'is_completed', 'due_date',
            'start_at', 'earliest_start_at', 'latest_finish_at', 'snoozed_until', 'backlog_date',
            'estimated_minutes', 'estimated_hours', 'actual_hours',
            'assigned_to', 'assigned_team', 'tags', 'notes', 'milestone', 'dependencies',
            'is_hard_due', 'parent', 'context_energy', 'context_location', 'recurrence_rule'
        )


class TaskToggleSerializer(serializers.Serializer):
    task = TaskSerializer(read_only=True)
    message = serializers.CharField(read_only=True)
