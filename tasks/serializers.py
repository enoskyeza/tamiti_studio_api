from rest_framework import serializers
from tasks.models import Task, TaskGroup, KanbanBoard, KanbanColumn
from accounts.models import Department
from taggit.serializers import TaggitSerializer, TagListSerializerField
from users.models import User


class TaskGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskGroup
        fields = '__all__'


class TaskSerializer(serializers.ModelSerializer):
    is_overdue = serializers.ReadOnlyField()
    project_name = serializers.CharField(source='project.name', read_only=True)
    assigned_to_email = serializers.EmailField(source='assigned_to.email', read_only=True)
    assigned_team_name = serializers.CharField(source='assigned_team.name', read_only=True)

    # Mockup API compatibility fields
    projectId = serializers.ReadOnlyField()
    assignedUsers = serializers.ReadOnlyField()
    assignedTeams = serializers.ReadOnlyField()
    dueDate = serializers.ReadOnlyField()
    estimatedHours = serializers.ReadOnlyField()
    actualHours = serializers.ReadOnlyField()
    createdAt = serializers.ReadOnlyField()
    updatedAt = serializers.ReadOnlyField()
    tags = serializers.SerializerMethodField()

    class Meta:
        model = Task
        fields = (
            'id', 'project', 'project_name', 'projectId', 'title', 'description', 'status',
            'priority', 'due_date', 'dueDate', 'start_at', 'earliest_start_at', 'latest_finish_at',
            'snoozed_until', 'backlog_date', 'estimated_minutes', 'estimated_hours', 'estimatedHours',
            'actual_hours', 'actualHours', 'assigned_to', 'assigned_to_email', 'assigned_users',
            'assigned_team', 'assigned_team_name', 'assigned_teams', 'assignedUsers', 'assignedTeams',
            'dependencies', 'milestone', 'origin_app', 'created_by', 'notes', 'tags',
            'position', 'is_completed', 'completed_at', 'is_hard_due', 'parent',
            'context_energy', 'context_location', 'recurrence_rule',
            'created_at', 'updated_at', 'createdAt', 'updatedAt', 'is_overdue'
        )
        read_only_fields = ('created_at', 'updated_at', 'completed_at')

    def get_tags(self, obj):
        """Return tags as string array to match mockup API"""
        return [tag.name for tag in obj.tags.all()]


class TaskCreateSerializer(TaggitSerializer, serializers.ModelSerializer):
    dependencies = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Task.objects.all(), required=False
    )
    assigned_users = serializers.PrimaryKeyRelatedField(
        many=True, queryset=User.objects.all(), required=False
    )
    assigned_teams = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Department.objects.all(), required=False
    )
    tags = TagListSerializerField(required=False)

    class Meta:
        model = Task
        fields = (
            'project', 'title', 'description', 'priority', 'due_date', 'start_at',
            'earliest_start_at', 'latest_finish_at', 'snoozed_until', 'backlog_date',
            'estimated_minutes', 'estimated_hours', 'assigned_to', 'assigned_users',
            'assigned_team', 'assigned_teams', 'notes', 'origin_app',
            'milestone', 'dependencies', 'tags', 'is_hard_due', 'parent', 'context_energy', 'context_location',
            'recurrence_rule'
        )


class TaskUpdateSerializer(TaggitSerializer, serializers.ModelSerializer):
    dependencies = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Task.objects.all(), required=False
    )
    assigned_users = serializers.PrimaryKeyRelatedField(
        many=True, queryset=User.objects.all(), required=False
    )
    assigned_teams = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Department.objects.all(), required=False
    )
    tags = TagListSerializerField(required=False)

    class Meta:
        model = Task
        fields = (
            'title', 'description', 'priority', 'status', 'is_completed', 'due_date',
            'start_at', 'earliest_start_at', 'latest_finish_at', 'snoozed_until', 'backlog_date',
            'estimated_minutes', 'estimated_hours', 'actual_hours',
            'assigned_to', 'assigned_users', 'assigned_team', 'assigned_teams', 'tags', 'notes', 'milestone', 'dependencies',
            'is_hard_due', 'parent', 'context_energy', 'context_location', 'recurrence_rule'
        )


class TaskToggleSerializer(serializers.Serializer):
    task = TaskSerializer(read_only=True)
    message = serializers.CharField(read_only=True)


class KanbanColumnSerializer(serializers.ModelSerializer):
    task_count = serializers.ReadOnlyField()
    is_wip_exceeded = serializers.ReadOnlyField()
    tasks = serializers.SerializerMethodField()

    class Meta:
        model = KanbanColumn
        fields = [
            'id', 'name', 'status_mapping', 'order', 'color', 'wip_limit',
            'task_count', 'is_wip_exceeded', 'tasks', 'created_at', 'updated_at'
        ]
        read_only_fields = ('created_at', 'updated_at')

    def get_tasks(self, obj):
        """Get tasks in this column ordered by kanban_position"""
        if obj.status_mapping:
            # Use status mapping to get tasks
            tasks = obj.board.project.tasks.filter(status=obj.status_mapping).order_by('kanban_position')
        else:
            # Use direct relationship
            tasks = obj.tasks.all().order_by('kanban_position')
        return TaskSerializer(tasks, many=True).data


class KanbanBoardSerializer(serializers.ModelSerializer):
    columns = KanbanColumnSerializer(many=True, read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)

    class Meta:
        model = KanbanBoard
        fields = ['id', 'name', 'project', 'project_name', 'columns', 'created_at', 'updated_at']
        read_only_fields = ('created_at', 'updated_at')


class TaskMoveSerializer(serializers.Serializer):
    """Serializer for moving tasks between columns"""
    target_column_id = serializers.IntegerField()
    position = serializers.IntegerField(required=False)

    def validate_target_column_id(self, value):
        try:
            KanbanColumn.objects.get(id=value)
        except KanbanColumn.DoesNotExist:
            raise serializers.ValidationError("Invalid column ID")
        return value


class TaskReorderSerializer(serializers.Serializer):
    """Serializer for reordering tasks within a column"""
    new_position = serializers.IntegerField(min_value=0)
