from django.db.models import TextChoices

class TaskStatus(TextChoices):
    TODO = 'todo', 'To Do'
    IN_PROGRESS = 'in_progress', 'In Progress'
    DONE = 'done', 'Done'

class ProjectStatus(TextChoices):
    PLANNING = 'planning', 'Planning'
    ACTIVE = 'active', 'Active'
    PAUSED = 'paused', 'Paused'
    REVIEW = 'review', 'Review'
    COMPLETE = 'complete', 'Complete'
    CANCELLED = 'cancelled', 'Cancelled'
    ARCHIVED = 'archived', 'Archived'

class PriorityLevel(TextChoices):
    LOW = 'low', 'Low'
    MEDIUM = 'medium', 'Medium'
    HIGH = 'high', 'High'
    CRITICAL = 'critical', 'Critical'

class ProjectRole(TextChoices):
    OWNER = 'owner', 'Owner'
    MANAGER = 'manager', 'Manager'
    CONTRIBUTOR = 'contributor', 'Contributor'
    VIEWER = 'viewer', 'Viewer'

class OriginApp(TextChoices):
    TASKS = 'tasks', 'Tasks'
    PROJECTS = 'projects', 'Projects'
    DIGITAL = 'digital', 'Digital'
    LEADS = 'leads', 'Leads'

