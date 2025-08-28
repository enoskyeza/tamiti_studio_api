from rest_framework import serializers


class ProjectSummarySerializer(serializers.Serializer):
    """Serializer for project summary statistics."""

    total = serializers.IntegerField()
    active = serializers.IntegerField()
    completed = serializers.IntegerField()


class TaskSummarySerializer(serializers.Serializer):
    """Serializer for task summary statistics."""

    total = serializers.IntegerField()
    completed = serializers.IntegerField()
    overdue = serializers.IntegerField()


class FinanceSummarySerializer(serializers.Serializer):
    """Serializer for aggregated financial information."""

    income = serializers.DecimalField(max_digits=12, decimal_places=2)
    expenses = serializers.DecimalField(max_digits=12, decimal_places=2)
    goals_count = serializers.IntegerField()


class RecentVisitSerializer(serializers.Serializer):
    """Serializer for recent field visits."""

    location = serializers.CharField()
    rep__email = serializers.EmailField()
    date_time = serializers.DateTimeField()


class FieldSummarySerializer(serializers.Serializer):
    """Serializer for field module statistics."""

    total_visits = serializers.IntegerField()
    recent = RecentVisitSerializer(many=True)


class LeadsSummarySerializer(serializers.Serializer):
    """Serializer for lead statistics."""

    total = serializers.IntegerField()
    won = serializers.IntegerField()
    lost = serializers.IntegerField()


class SocialSummarySerializer(serializers.Serializer):
    """Serializer for social media post statistics."""

    draft = serializers.IntegerField()
    published = serializers.IntegerField()
    platforms = serializers.ListField(child=serializers.CharField())


class DashboardKPISerializer(serializers.Serializer):
    """Serializer aggregating KPI metrics from all modules."""

    projects = ProjectSummarySerializer()
    tasks = TaskSummarySerializer()
    finance = FinanceSummarySerializer()
    field = FieldSummarySerializer()
    leads = LeadsSummarySerializer()
    social = SocialSummarySerializer()
