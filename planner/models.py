from datetime import timedelta, date
from decimal import Decimal

from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator

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

    def __str__(self):
        who = self.owner_user or self.owner_team
        return f"TimeBlock({who}) {self.title} [{self.start.strftime('%H:%M')}-{self.end.strftime('%H:%M')}]"


class WorkGoal(BaseModel):
    """Work goals separate from Finance goals for productivity tracking"""
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    target_date = models.DateField(null=True, blank=True)
    owner_user = models.ForeignKey(User, null=True, blank=True, on_delete=models.CASCADE, related_name='work_goals')
    owner_team = models.ForeignKey(Department, null=True, blank=True, on_delete=models.CASCADE, related_name='work_goals')
    project = models.ForeignKey('projects.Project', null=True, blank=True, on_delete=models.CASCADE, related_name='work_goals')
    tags = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    
    # Computed progress fields (updated by signals)
    progress_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    total_tasks = models.PositiveIntegerField(default=0)
    completed_tasks = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['target_date']),
            models.Index(fields=['is_active']),
            models.Index(fields=['owner_user', 'is_active']),
            models.Index(fields=['owner_team', 'is_active']),
        ]
    
    def __str__(self):
        who = self.owner_user or self.owner_team
        return f"WorkGoal({who}) {self.name}"
    
    def update_progress(self):
        """Update progress based on linked tasks"""
        from tasks.models import Task
        if self.project:
            tasks = Task.objects.filter(project=self.project)
            self.total_tasks = tasks.count()
            self.completed_tasks = tasks.filter(is_completed=True).count()
            self.progress_percentage = (self.completed_tasks / self.total_tasks * 100) if self.total_tasks > 0 else 0
        else:
            self.total_tasks = 0
            self.completed_tasks = 0
            self.progress_percentage = 0
        self.save(update_fields=['progress_percentage', 'total_tasks', 'completed_tasks'])


class DailyReview(BaseModel):
    """Daily productivity review and reflection"""
    date = models.DateField()
    owner_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='daily_reviews')
    
    # Reflection fields
    summary = models.TextField(blank=True, help_text="Overall day summary")
    mood = models.CharField(max_length=20, choices=[
        ('excellent', 'Excellent'),
        ('good', 'Good'),
        ('neutral', 'Neutral'),
        ('poor', 'Poor'),
        ('terrible', 'Terrible'),
    ], null=True, blank=True)
    highlights = models.TextField(blank=True, help_text="Key accomplishments")
    lessons = models.TextField(blank=True, help_text="What did you learn?")
    tomorrow_top3 = models.JSONField(default=list, blank=True, help_text="Top 3 priorities for tomorrow")
    
    # Computed productivity metrics (auto-calculated)
    tasks_planned = models.PositiveIntegerField(default=0)
    tasks_completed = models.PositiveIntegerField(default=0)
    completion_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    focus_time_minutes = models.PositiveIntegerField(default=0)
    break_time_minutes = models.PositiveIntegerField(default=0)
    productivity_score = models.DecimalField(max_digits=5, decimal_places=2, default=0, help_text="Algorithmic productivity score 0-100")
    
    # Streak tracking
    current_streak = models.PositiveIntegerField(default=0, help_text="Current daily completion streak")
    
    class Meta:
        unique_together = ['date', 'owner_user']
        ordering = ['-date']
        indexes = [
            models.Index(fields=['date']),
            models.Index(fields=['owner_user', 'date']),
            models.Index(fields=['productivity_score']),
        ]
    
    def __str__(self):
        return f"DailyReview({self.owner_user}) {self.date} - {self.productivity_score}%"
    
    def calculate_metrics(self):
        """Calculate productivity metrics for the day"""
        from tasks.models import Task
        
        # Get tasks for this day
        day_start = timezone.make_aware(timezone.datetime.combine(self.date, timezone.datetime.min.time()))
        day_end = day_start + timedelta(days=1)
        
        # Tasks that were scheduled for this day
        scheduled_tasks = Task.objects.filter(
            assigned_to=self.owner_user,
            time_blocks__start__gte=day_start,
            time_blocks__start__lt=day_end
        ).distinct()
        
        # Tasks completed on this day
        completed_tasks = scheduled_tasks.filter(
            is_completed=True,
            completed_at__gte=day_start,
            completed_at__lt=day_end
        )
        
        self.tasks_planned = scheduled_tasks.count()
        self.tasks_completed = completed_tasks.count()
        self.completion_rate = (self.tasks_completed / self.tasks_planned * 100) if self.tasks_planned > 0 else 0
        
        # Calculate focus and break time from time blocks
        blocks = TimeBlock.objects.filter(
            owner_user=self.owner_user,
            start__gte=day_start,
            start__lt=day_end,
            status__in=['completed', 'active']
        )
        
        self.focus_time_minutes = sum(
            block.duration_minutes for block in blocks if not block.is_break
        )
        self.break_time_minutes = sum(
            block.duration_minutes for block in blocks if block.is_break
        )
        
        # Calculate productivity score (algorithmic)
        self.productivity_score = self._calculate_productivity_score()
        
        # Update streak
        self._update_streak()
        
        self.save()
    
    def _calculate_productivity_score(self) -> Decimal:
        """Algorithmic productivity score calculation"""
        score = Decimal('0')
        
        # Base completion rate (40% weight)
        score += self.completion_rate * Decimal('0.4')
        
        # Focus time bonus (30% weight) - optimal 4-6 hours
        optimal_focus = 300  # 5 hours in minutes
        focus_ratio = min(self.focus_time_minutes / optimal_focus, 1.0)
        score += Decimal(str(focus_ratio * 30))
        
        # Break balance bonus (15% weight) - good break to focus ratio
        if self.focus_time_minutes > 0:
            break_ratio = self.break_time_minutes / self.focus_time_minutes
            optimal_break_ratio = 0.2  # 20% breaks
            break_score = max(0, 15 - abs(break_ratio - optimal_break_ratio) * 75)
            score += Decimal(str(break_score))
        
        # Consistency bonus (15% weight) - based on streak
        streak_bonus = min(self.current_streak * 2, 15)
        score += Decimal(str(streak_bonus))
        
        return min(score, Decimal('100'))
    
    def _update_streak(self):
        """Update completion streak"""
        if self.completion_rate >= 70:  # 70% completion maintains streak
            yesterday = self.date - timedelta(days=1)
            try:
                yesterday_review = DailyReview.objects.get(owner_user=self.owner_user, date=yesterday)
                self.current_streak = yesterday_review.current_streak + 1
            except DailyReview.DoesNotExist:
                self.current_streak = 1
        else:
            self.current_streak = 0


class ProductivityInsight(BaseModel):
    """Computed productivity insights and patterns"""
    owner_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='productivity_insights')
    insight_type = models.CharField(max_length=50, choices=[
        ('peak_hours', 'Peak Productivity Hours'),
        ('task_duration', 'Optimal Task Duration'),
        ('break_pattern', 'Optimal Break Pattern'),
        ('weekly_trend', 'Weekly Productivity Trend'),
        ('completion_pattern', 'Task Completion Pattern'),
    ])
    
    # Insight data
    data = models.JSONField(default=dict)
    confidence_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    sample_size = models.PositiveIntegerField(default=0)
    
    # Validity
    valid_from = models.DateField()
    valid_until = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ['owner_user', 'insight_type']
        ordering = ['-confidence_score']
        indexes = [
            models.Index(fields=['owner_user', 'insight_type']),
            models.Index(fields=['is_active', 'confidence_score']),
        ]
    
    def __str__(self):
        return f"Insight({self.owner_user}) {self.insight_type} - {self.confidence_score}%"

