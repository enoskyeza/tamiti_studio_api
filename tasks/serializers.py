from rest_framework import serializers
from tasks.models import Task, TaskGroup
from taggit.serializers import TaggitSerializer, TagListSerializerField


class TaskGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskGroup
        fields = '__all__'


class TaskSerializer(serializers.ModelSerializer):
    is_overdue = serializers.ReadOnlyField()
    project_name = serializers.CharField(source='project.name', read_only=True)
    assigned_to_email = serializers.EmailField(source='assigned_to.email', read_only=True)

    class Meta:
        model = Task
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at', 'completed_at')


class TaskCreateSerializer(TaggitSerializer, serializers.ModelSerializer):
    dependencies = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Task.objects.all(), required=False
    )
    tags = TagListSerializerField(required=False)

    class Meta:
        model = Task
        fields = (
            'project', 'title', 'description', 'priority', 'due_date',
            'estimated_hours', 'assigned_to',
            'tags', 'notes', 'origin_app', 'milestone', 'dependencies'
        )


class TaskUpdateSerializer(TaggitSerializer, serializers.ModelSerializer):
    dependencies = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Task.objects.all(), required=False
    )
    tags = TagListSerializerField(required=False)

    class Meta:
        model = Task
        fields = (
            'title', 'description', 'priority', 'is_completed', 'due_date',
            'estimated_hours', 'actual_hours', 'assigned_to',
            'tags', 'notes', 'milestone', 'dependencies'
        )


class TaskToggleSerializer(serializers.Serializer):
    task = TaskSerializer(read_only=True)
    message = serializers.CharField(read_only=True)

