from django.db import models
from django.contrib.contenttypes.fields import GenericRelation
from django.utils import timezone

from core.models import BaseModel
from users.models import User
from projects.models import Project, Milestone
from accounts.models import Department
from common.enums import TaskStatus, PriorityLevel, OriginApp, EnergyLevel
from taggit.managers import TaggableManager



class Task(BaseModel):
    comments = GenericRelation('comments.Comment', related_query_name='tasks')
    project = models.ForeignKey(Project, related_name='tasks', on_delete=models.CASCADE, null=True, blank=True)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=32, choices=TaskStatus.choices, default=TaskStatus.TODO)
    priority = models.CharField(max_length=20, choices=PriorityLevel.choices, default=PriorityLevel.MEDIUM)
    due_date = models.DateTimeField(null=True, blank=True)
    # Planning and scheduling fields
    start_at = models.DateTimeField(null=True, blank=True)
    earliest_start_at = models.DateTimeField(null=True, blank=True)
    latest_finish_at = models.DateTimeField(null=True, blank=True)
    snoozed_until = models.DateTimeField(null=True, blank=True)
    backlog_date = models.DateField(null=True, blank=True)
    estimated_minutes = models.PositiveIntegerField(null=True, blank=True)
    estimated_hours = models.PositiveIntegerField(null=True, blank=True)
    actual_hours = models.PositiveIntegerField(default=0, null=True, blank=True)
    assigned_to = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='tasks')
    assigned_team = models.ForeignKey(Department, null=True, blank=True, on_delete=models.SET_NULL, related_name='tasks')
    dependencies = models.ManyToManyField('self', blank=True, symmetrical=False, related_name='dependents')
    milestone = models.ForeignKey(Milestone, null=True, blank=True, on_delete=models.SET_NULL)
    origin_app = models.CharField(max_length=64, choices=OriginApp.choices, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_tasks')
    tags = TaggableManager(blank=True)
    notes = models.TextField(blank=True)
    position = models.PositiveIntegerField(default=0)
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    is_hard_due = models.BooleanField(default=False)
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='subtasks')
    context_energy = models.CharField(max_length=16, choices=EnergyLevel.choices, null=True, blank=True)
    context_location = models.CharField(max_length=100, null=True, blank=True)
    recurrence_rule = models.TextField(null=True, blank=True)

    class Meta:
        ordering = ['is_completed', 'position', 'due_date']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['is_completed']),
            models.Index(fields=['due_date']),
            models.Index(fields=['snoozed_until']),
            models.Index(fields=['assigned_to']),
            models.Index(fields=['assigned_team']),
        ]

    def __str__(self):
        proj = self.project.name if self.project else "(personal)"
        return f"{proj}: {self.title}"

    def save(self, *args, **kwargs):
        if self.is_completed and not self.completed_at:
            self.completed_at = timezone.now()
            if self.status != TaskStatus.DONE:
                self.status = TaskStatus.DONE
        elif not self.is_completed:
            self.completed_at = None
            if self.status == TaskStatus.DONE:
                self.status = TaskStatus.TODO

        super().save(*args, **kwargs)
        if self.project:
            self.project.update_completion_percentage()

    @property
    def is_overdue(self):
        return self.due_date and not self.is_completed and timezone.now() > self.due_date


class TaskGroup(BaseModel):
    project = models.ForeignKey(Project, related_name='task_groups', on_delete=models.CASCADE)
    name = models.CharField(max_length=100)  # e.g. 'To Do', 'In Progress', 'Done'
    order = models.PositiveIntegerField(default=0)
