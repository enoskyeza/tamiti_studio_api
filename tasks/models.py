from django.db import models
from django.utils import timezone

from core.models import BaseModel
from users.models import User
from projects.models import Project, Milestone
from common.enums import TaskStatus, PriorityLevel, OriginApp
from taggit.managers import TaggableManager



class Task(BaseModel):
    project = models.ForeignKey(Project, related_name='tasks', on_delete=models.CASCADE, null=True, blank=True)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=32, choices=TaskStatus.choices, default=TaskStatus.TODO)
    priority = models.CharField(max_length=20, choices=PriorityLevel.choices, default=PriorityLevel.MEDIUM)
    due_date = models.DateTimeField(null=True, blank=True)
    estimated_hours = models.PositiveIntegerField(null=True, blank=True)
    actual_hours = models.PositiveIntegerField(default=0, null=True, blank=True)
    assigned_to = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='tasks')
    dependencies = models.ManyToManyField('self', blank=True, symmetrical=False, related_name='dependents')
    milestone = models.ForeignKey(Milestone, null=True, blank=True, on_delete=models.SET_NULL)
    origin_app = models.CharField(max_length=64, choices=OriginApp.choices, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_tasks')
    tags = TaggableManager(blank=True)
    notes = models.TextField(blank=True)
    position = models.PositiveIntegerField(default=0)
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['is_completed', 'position', 'due_date']

    def __str__(self):
        return f"{self.project.name}: {self.title}"

    def save(self, *args, **kwargs):
        if self.is_completed and not self.completed_at:
            self.completed_at = timezone.now()
        elif not self.is_completed:
            self.completed_at = None

        super().save(*args, **kwargs)
        self.project.update_completion_percentage()

    @property
    def is_overdue(self):
        return self.due_date and not self.is_completed and timezone.now() > self.due_date


class TaskGroup(BaseModel):
    project = models.ForeignKey(Project, related_name='task_groups', on_delete=models.CASCADE)
    name = models.CharField(max_length=100)  # e.g. 'To Do', 'In Progress', 'Done'
    order = models.PositiveIntegerField(default=0)
