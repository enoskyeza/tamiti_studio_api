from rest_framework import serializers
from projects.models import Project, ProjectMember, Milestone, ProjectComment
from tasks.models import Task


class MilestoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = Milestone
        fields = '__all__'
        read_only_fields = ('achievement_date', 'created_at')


class ProjectCommentSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)

    class Meta:
        model = ProjectComment
        fields = '__all__'
        read_only_fields = ('user', 'created_at')


class ProjectMemberSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = ProjectMember
        fields = '__all__'
        read_only_fields = ('created_at',)


class ProjectSummarySerializer(serializers.ModelSerializer):
    task_count = serializers.SerializerMethodField()
    completed_task_count = serializers.SerializerMethodField()
    is_overdue = serializers.ReadOnlyField()

    class Meta:
        model = Project
        fields = (
            'id', 'name', 'status', 'priority', 'completion_percentage',
            'due_date', 'task_count', 'completed_task_count', 'is_overdue'
        )

    def get_task_count(self, obj):
        return obj.tasks.count()

    def get_completed_task_count(self, obj):
        return obj.tasks.filter(is_completed=True).count()


class ProjectSerializer(serializers.ModelSerializer):
    tasks = serializers.SerializerMethodField()
    milestones = MilestoneSerializer(many=True, read_only=True)
    comments = ProjectCommentSerializer(many=True, read_only=True)
    members = ProjectMemberSerializer(many=True, read_only=True)
    task_count = serializers.SerializerMethodField()
    completed_task_count = serializers.SerializerMethodField()
    is_overdue = serializers.ReadOnlyField()

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
