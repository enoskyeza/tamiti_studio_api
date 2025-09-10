from rest_framework import serializers
from projects.models import Project, ProjectMember, Milestone
from tasks.models import Task


class MilestoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = Milestone
        fields = '__all__'
        read_only_fields = ('achievement_date', 'created_at')


class ProjectMemberSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_avatar = serializers.ImageField(source='user.avatar', read_only=True)
    user_username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = ProjectMember
        fields = '__all__'
        read_only_fields = ('created_at',)


class ProjectSummarySerializer(serializers.ModelSerializer):
    task_count = serializers.SerializerMethodField()
    completed_task_count = serializers.SerializerMethodField()
    comments_count = serializers.SerializerMethodField()
    is_overdue = serializers.ReadOnlyField()
    members = ProjectMemberSerializer(many=True, read_only=True)

    class Meta:
        model = Project
        fields = (
            'id', 'name', 'status', 'priority', 'completion_percentage',
            'due_date', 'task_count', 'completed_task_count', 'comments_count', 'is_overdue',
            'members', 'description', 'client_name', 'budget', 'tags'
        )

    def get_task_count(self, obj):
        return obj.tasks.count()

    def get_completed_task_count(self, obj):
        return obj.tasks.filter(is_completed=True).count()

    def get_comments_count(self, obj):
        return obj.comments.count()


class ProjectSerializer(serializers.ModelSerializer):
    tasks = serializers.SerializerMethodField()
    milestones = MilestoneSerializer(many=True, read_only=True)
    comments = serializers.SerializerMethodField()
    members = ProjectMemberSerializer(many=True, read_only=True)
    task_count = serializers.SerializerMethodField()
    completed_task_count = serializers.SerializerMethodField()
    is_overdue = serializers.ReadOnlyField()
    progress = serializers.ReadOnlyField()
    startDate = serializers.ReadOnlyField()
    endDate = serializers.ReadOnlyField()
    clientName = serializers.ReadOnlyField()
    clientEmail = serializers.ReadOnlyField()
    assignedUsers = serializers.ReadOnlyField()
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)

    class Meta:
        model = Project
        fields = '__all__'
        read_only_fields = ('created_by', 'completion_percentage', 'created_at', 'updated_at')

    def get_task_count(self, obj):
        return obj.tasks.count()

    def get_completed_task_count(self, obj):
        return obj.tasks.filter(is_completed=True).count()

    def get_tasks(self, obj):
        from tasks.serializers import TaskSerializer  # avoid circular import
        return TaskSerializer(obj.tasks.all(), many=True).data

    def get_comments(self, obj):
        # Use global comments serializer lazily to avoid circular imports
        from comments.serializers import CommentSerializer
        return CommentSerializer(obj.comments.all(), many=True).data
