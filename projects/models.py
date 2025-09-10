from django.db import models
from django.contrib.contenttypes.fields import GenericRelation
from django.utils import timezone

from core.models import BaseModel
from users.models import User
from common.enums import ProjectStatus, ProjectRole, PriorityLevel


class Project(BaseModel):
    comments = GenericRelation('comments.Comment', related_query_name='projects')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    client_name = models.CharField(max_length=255, blank=True)
    client_email = models.EmailField(blank=True)
    status = models.CharField(max_length=32, choices=ProjectStatus.choices, default=ProjectStatus.PLANNING)
    priority = models.CharField(max_length=20, choices=PriorityLevel.choices, default=PriorityLevel.MEDIUM)
    start_date = models.DateField()
    due_date = models.DateField()
    estimated_hours = models.PositiveIntegerField(null=True, blank=True)
    actual_hours = models.PositiveIntegerField(default=0)
    budget = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    completion_percentage = models.PositiveIntegerField(default=0)
    tags = models.JSONField(default=list, blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='owned_projects')

    def __str__(self):
        return self.name

    def update_completion_percentage(self):
        total_tasks = self.tasks.count()
        if total_tasks == 0:
            self.completion_percentage = 0
        else:
            completed_tasks = self.tasks.filter(is_completed=True).count()
            self.completion_percentage = int((completed_tasks / total_tasks) * 100)
        self.save(update_fields=['completion_percentage'])

    @property
    def is_overdue(self):
        if self.due_date and self.status not in [ProjectStatus.COMPLETE, ProjectStatus.CANCELLED]:
            return timezone.now().date() > self.due_date
        return False

    @property
    def progress(self):
        """Alias for completion_percentage to match mockup API"""
        return self.completion_percentage

    @property
    def startDate(self):
        """Alias for start_date to match mockup API"""
        return self.start_date.isoformat() if self.start_date else None

    @property
    def endDate(self):
        """Alias for due_date to match mockup API"""
        return self.due_date.isoformat() if self.due_date else None

    @property
    def clientName(self):
        """Alias for client_name to match mockup API"""
        return self.client_name

    @property
    def clientEmail(self):
        """Alias for client_email to match mockup API"""
        return self.client_email

    @property
    def assignedUsers(self):
        """Return list of assigned user IDs to match mockup API"""
        return list(self.members.values_list('user_id', flat=True))

    class Meta:
        # Deterministic default ordering for stable pagination and list results
        ordering = ['-updated_at', '-id']


class ProjectMember(BaseModel):
    project = models.ForeignKey(Project, related_name='members', on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=32, choices=ProjectRole.choices)

    class Meta:
        unique_together = ('project', 'user')


class Milestone(BaseModel):
    project = models.ForeignKey(Project, related_name='milestones', on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    due_date = models.DateField()
    completed = models.BooleanField(default=False)
    reward = models.CharField(max_length=200, blank=True)
    achievement_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.project.name}: {self.name}"

    def save(self, *args, **kwargs):
        if self.completed and not self.achievement_date:
            self.achievement_date = timezone.now().date()
        elif not self.completed:
            self.achievement_date = None
        super().save(*args, **kwargs)


