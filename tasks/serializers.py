from rest_framework import serializers
from tasks.models import Task, TaskGroup, KanbanBoard, KanbanColumn, BacklogItem, TaskChecklist
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
    tasks_count = serializers.SerializerMethodField()
    
    class Meta:
        model = KanbanColumn
        fields = '__all__'
    
    def get_tasks_count(self, obj):
        return obj.tasks.count()


class TaskChecklistSerializer(serializers.ModelSerializer):
    """Serializer for task checklist items"""
    
    class Meta:
        model = TaskChecklist
        fields = ['id', 'title', 'is_completed', 'completed_at', 'position', 'created_at', 'updated_at']
        read_only_fields = ['completed_at', 'created_at', 'updated_at']


class BacklogItemSerializer(serializers.ModelSerializer):
    """Serializer for backlog items"""
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    converted_task_title = serializers.CharField(source='converted_to_task.title', read_only=True)
    
    class Meta:
        model = BacklogItem
        fields = [
            'id', 'title', 'source', 'created_by', 'created_by_name',
            'converted_to_task', 'converted_task_title', 'is_converted',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_by', 'converted_to_task', 'is_converted', 'created_at', 'updated_at']


class BacklogToTaskSerializer(serializers.Serializer):
    """Serializer for converting backlog items to tasks"""
    description = serializers.CharField(required=False, allow_blank=True)
    priority = serializers.ChoiceField(choices=Task._meta.get_field('priority').choices, required=False)
    due_date = serializers.DateTimeField(required=False, allow_null=True)
    estimated_hours = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    estimated_minutes = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    project = serializers.IntegerField(required=False, allow_null=True)
    assigned_to = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), required=False, allow_null=True)
    tags = serializers.ListField(child=serializers.CharField(), required=False)
    
    def validate_project(self, value):
        """Validate that the user has access to the project"""
        if value is None:
            return value
        
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            from projects.models import Project
            try:
                project = Project.objects.filter(
                    created_by=request.user
                ).get(id=value)
                return project
            except Project.DoesNotExist:
                raise serializers.ValidationError("Project not found or access denied")
        return value


class TaskDetailSerializer(TaskSerializer):
    """Extended task serializer with checklist items"""
    checklist_items = TaskChecklistSerializer(many=True, read_only=True)
    checklist_completed_count = serializers.SerializerMethodField()
    checklist_total_count = serializers.SerializerMethodField()
    checklist_progress_percentage = serializers.SerializerMethodField()
    
    class Meta(TaskSerializer.Meta):
        fields = list(TaskSerializer.Meta.fields) + [
            'checklist_items', 'checklist_completed_count', 
            'checklist_total_count', 'checklist_progress_percentage'
        ]
    
    def get_checklist_completed_count(self, obj):
        return obj.checklist_items.filter(is_completed=True).count()
    
    def get_checklist_total_count(self, obj):
        return obj.checklist_items.count()
    
    def get_checklist_progress_percentage(self, obj):
        total = obj.checklist_items.count()
        if total == 0:
            return 0
        completed = obj.checklist_items.filter(is_completed=True).count()
        return round((completed / total) * 100, 1)


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
