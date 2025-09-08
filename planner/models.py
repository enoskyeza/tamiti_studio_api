from datetime import timedelta

from django.db import models
from django.utils import timezone

from core.models import BaseModel
from users.models import User
from accounts.models import Department
from tasks.models import Task
from common.enums import BlockStatus


class BreakPolicy(BaseModel):
    owner_user = models.ForeignKey(User, null=True, blank=True, on_delete=models.CASCADE, related_name='break_policies')
    owner_team = models.ForeignKey(Department, null=True, blank=True, on_delete=models.CASCADE, related_name='break_policies')
    focus_minutes = models.PositiveIntegerField(default=25)
    break_minutes = models.PositiveIntegerField(default=5)
    long_break_minutes = models.PositiveIntegerField(default=15)
    cycle_count = models.PositiveIntegerField(default=4)
    active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['owner_user', 'owner_team'], name='uniq_break_policy_per_owner')
        ]

    def __str__(self):
        who = self.owner_user or self.owner_team
        return f"BreakPolicy({who}) {self.focus_minutes}/{self.break_minutes}"


class AvailabilityTemplate(BaseModel):
    owner_user = models.ForeignKey(User, null=True, blank=True, on_delete=models.CASCADE, related_name='availability_templates')
    owner_team = models.ForeignKey(Department, null=True, blank=True, on_delete=models.CASCADE, related_name='availability_templates')
    day_of_week = models.IntegerField(help_text='0=Mon .. 6=Sun')
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        ordering = ['day_of_week', 'start_time']

    def __str__(self):
        who = self.owner_user or self.owner_team
        return f"Avail({who}) d{self.day_of_week} {self.start_time}-{self.end_time}"


class CalendarEvent(BaseModel):
    owner_user = models.ForeignKey(User, null=True, blank=True, on_delete=models.CASCADE, related_name='calendar_events')
    owner_team = models.ForeignKey(Department, null=True, blank=True, on_delete=models.CASCADE, related_name='calendar_events')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    start = models.DateTimeField()
    end = models.DateTimeField()
    is_busy = models.BooleanField(default=True)
    source = models.CharField(max_length=32, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['start']),
            models.Index(fields=['end']),
        ]

    def __str__(self):
        who = self.owner_user or self.owner_team
        return f"Event({who}) {self.title}"


class TimeBlock(BaseModel):
    owner_user = models.ForeignKey(User, null=True, blank=True, on_delete=models.CASCADE, related_name='time_blocks')
    owner_team = models.ForeignKey(Department, null=True, blank=True, on_delete=models.CASCADE, related_name='time_blocks')
    task = models.ForeignKey(Task, null=True, blank=True, on_delete=models.SET_NULL, related_name='time_blocks')
    title = models.CharField(max_length=255)
    start = models.DateTimeField()
    end = models.DateTimeField()
    status = models.CharField(max_length=20, choices=BlockStatus.choices, default=BlockStatus.PLANNED)
    is_break = models.BooleanField(default=False)
    source = models.CharField(max_length=16, default='auto', help_text='auto|manual')

    class Meta:
        ordering = ['start']
        indexes = [
            models.Index(fields=['start']),
            models.Index(fields=['end']),
            models.Index(fields=['status']),
        ]

    @property
    def duration_minutes(self) -> int:
        return int((self.end - self.start) / timedelta(minutes=1))

