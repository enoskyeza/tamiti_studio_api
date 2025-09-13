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
    assigned_users = models.ManyToManyField(User, blank=True, related_name='assigned_tasks')
    assigned_team = models.ForeignKey(Department, null=True, blank=True, on_delete=models.SET_NULL, related_name='tasks')
    assigned_teams = models.ManyToManyField(Department, blank=True, related_name='team_tasks')
    dependencies = models.ManyToManyField('self', blank=True, symmetrical=False, related_name='dependents')
    milestone = models.ForeignKey(Milestone, null=True, blank=True, on_delete=models.SET_NULL)
    origin_app = models.CharField(max_length=64, choices=OriginApp.choices, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_tasks')
    tags = TaggableManager(blank=True)
    notes = models.TextField(blank=True)
    position = models.PositiveIntegerField(default=0)
    kanban_column = models.ForeignKey('KanbanColumn', null=True, blank=True, on_delete=models.SET_NULL, related_name='tasks')
    kanban_position = models.PositiveIntegerField(default=0)  # Position within the kanban column
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    is_hard_due = models.BooleanField(default=False)
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='subtasks')
    context_energy = models.CharField(max_length=16, choices=EnergyLevel.choices, null=True, blank=True)
    context_location = models.CharField(max_length=100, null=True, blank=True)
    recurrence_rule = models.TextField(null=True, blank=True)

    class Meta:
        ordering = ['is_completed', 'kanban_position', 'position', 'due_date']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['is_completed']),
            models.Index(fields=['due_date']),
            models.Index(fields=['snoozed_until']),
            models.Index(fields=['assigned_to']),
            models.Index(fields=['assigned_team']),
            models.Index(fields=['kanban_column', 'kanban_position']),
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

    @property
    def projectId(self):
        """Alias for project_id to match mockup API"""
        return self.project_id

    @property
    def assignedUsers(self):
        """Return list of assigned user IDs to match mockup API"""
        # Combine single assigned_to with multiple assigned_users
        user_ids = list(self.assigned_users.values_list('id', flat=True))
        if self.assigned_to_id and self.assigned_to_id not in user_ids:
            user_ids.append(self.assigned_to_id)
        return user_ids

    @property
    def assignedTeams(self):
        """Return list of assigned team IDs to match mockup API"""
        # Combine single assigned_team with multiple assigned_teams
        team_ids = list(self.assigned_teams.values_list('id', flat=True))
        if self.assigned_team_id and self.assigned_team_id not in team_ids:
            team_ids.append(self.assigned_team_id)
        return team_ids

    @property
    def dueDate(self):
        """Alias for due_date to match mockup API"""
        return self.due_date.isoformat() if self.due_date else None

    @property
    def estimatedHours(self):
        """Alias for estimated_hours to match mockup API"""
        return self.estimated_hours

    @property
    def actualHours(self):
        """Alias for actual_hours to match mockup API"""
        return self.actual_hours

    @property
    def createdAt(self):
        """Alias for created_at to match mockup API"""
        return self.created_at.isoformat() if self.created_at else None

    @property
    def updatedAt(self):
        """Alias for updated_at to match mockup API"""
        return self.updated_at.isoformat() if self.updated_at else None

    def move_to_column(self, target_column, position=None):
        """Move task to a different Kanban column"""
        if position is None:
            # Move to the end of the target column
            max_position = Task.objects.filter(kanban_column=target_column).aggregate(
                models.Max('kanban_position')
            )['kanban_position__max'] or 0
            position = max_position + 1
        
        # Update other tasks in the target column
        Task.objects.filter(
            kanban_column=target_column,
            kanban_position__gte=position
        ).update(kanban_position=models.F('kanban_position') + 1)
        
        # Update this task
        self.kanban_column = target_column
        self.kanban_position = position
        
        # Update status if column has status mapping
        if target_column and target_column.status_mapping:
            self.status = target_column.status_mapping
        
        self.save()

    def reorder_in_column(self, new_position):
        """Reorder task within the same column"""
        if not self.kanban_column:
            return
        
        old_position = self.kanban_position
        if old_position == new_position:
            return
        
        # Get tasks in the same column
        column_tasks = Task.objects.filter(kanban_column=self.kanban_column)
        
        if new_position > old_position:
            # Moving down - shift tasks up
            column_tasks.filter(
                kanban_position__gt=old_position,
                kanban_position__lte=new_position
            ).update(kanban_position=models.F('kanban_position') - 1)
        else:
            # Moving up - shift tasks down
            column_tasks.filter(
                kanban_position__gte=new_position,
                kanban_position__lt=old_position
            ).update(kanban_position=models.F('kanban_position') + 1)
        
        self.kanban_position = new_position
        self.save()


class KanbanBoard(BaseModel):
    """Represents a Kanban board for a project"""
    project = models.OneToOneField(Project, related_name='kanban_board', on_delete=models.CASCADE)
    name = models.CharField(max_length=200, default="Project Board")
    
    def __str__(self):
        return self.title


class BacklogItem(BaseModel):
    """
    Simple backlog for capturing ideas and tasks without detailed planning.
    Can be converted to full tasks later.
    """
    class Source(models.TextChoices):
        PERSONAL = 'personal', 'Personal'
        WORK = 'work', 'Work'
        CLIENT = 'client', 'Client'
    
    title = models.CharField(max_length=255)
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.PERSONAL)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='backlog_items')
    converted_to_task = models.ForeignKey(Task, null=True, blank=True, on_delete=models.SET_NULL, related_name='source_backlog_item')
    is_converted = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['created_by', 'source']),
            models.Index(fields=['created_by', 'is_converted']),
        ]
    
    def __str__(self):
        return f"{self.title} ({self.get_source_display()})"
    
    def convert_to_task(self, **task_data):
        """
        Convert this backlog item to a full task.
        Returns the created task.
        """
        if self.is_converted:
            return self.converted_to_task
        
        # Set default values from backlog item
        task_defaults = {
            'title': self.title,
            'created_by': self.created_by,
            'assigned_to': self.created_by,
            'origin_app': OriginApp.TASKS,
        }
        
        # Override with provided task_data
        task_defaults.update(task_data)
        
        # Create the task
        task = Task.objects.create(**task_defaults)
        
        # Mark this backlog item as converted
        self.converted_to_task = task
        self.is_converted = True
        self.save(update_fields=['converted_to_task', 'is_converted', 'updated_at'])
        
        return task


class TaskChecklist(BaseModel):
    """
    Checklist items for tasks to break down work into smaller actionable items.
    """
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='checklist_items')
    title = models.CharField(max_length=255)
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    position = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['position', 'created_at']
        indexes = [
            models.Index(fields=['task', 'position']),
            models.Index(fields=['task', 'is_completed']),
        ]
    
    def __str__(self):
        status = "✓" if self.is_completed else "○"
        return f"{status} {self.title}"
    
    def mark_completed(self):
        """Mark this checklist item as completed."""
        if not self.is_completed:
            self.is_completed = True
            self.completed_at = timezone.now()
            self.save(update_fields=['is_completed', 'completed_at', 'updated_at'])
    
    def mark_incomplete(self):
        """Mark this checklist item as incomplete."""
        if self.is_completed:
            self.is_completed = False
            self.completed_at = None
            self.save(update_fields=['is_completed', 'completed_at', 'updated_at'])


class KanbanColumn(BaseModel):
    """Represents a column in a Kanban board"""
    board = models.ForeignKey(KanbanBoard, related_name='columns', on_delete=models.CASCADE)
    name = models.CharField(max_length=100)  # e.g. 'To Do', 'In Progress', 'Review', 'Done'
    status_mapping = models.CharField(max_length=32, choices=TaskStatus.choices, null=True, blank=True)
    order = models.PositiveIntegerField(default=0)
    color = models.CharField(max_length=7, default="#6B7280")  # Hex color for the column
    wip_limit = models.PositiveIntegerField(null=True, blank=True)  # Work In Progress limit
    
    class Meta:
        ordering = ['order']
        unique_together = ('board', 'order')
    
    def __str__(self):
        return f"{self.board.project.name} - {self.name}"
    
    @property
    def task_count(self):
        """Get count of tasks in this column"""
        if self.status_mapping:
            return self.board.project.tasks.filter(status=self.status_mapping).count()
        return self.tasks.count()
    
    @property
    def is_wip_exceeded(self):
        """Check if WIP limit is exceeded"""
        if self.wip_limit:
            return self.task_count > self.wip_limit
        return False


class TaskGroup(BaseModel):
    """Legacy model - keeping for backward compatibility"""
    project = models.ForeignKey(Project, related_name='task_groups', on_delete=models.CASCADE)
    name = models.CharField(max_length=100)  # e.g. 'To Do', 'In Progress', 'Done'
    order = models.PositiveIntegerField(default=0)
