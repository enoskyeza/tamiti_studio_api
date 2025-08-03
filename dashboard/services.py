from projects.models import Project
from tasks.models import Task
from finance.models import Transaction, Goal
from field.models import FieldVisit
from leads.models import Lead
from digital.models import SocialPost

def get_project_summary(user):
    projects = Project.objects.filter(created_by=user)
    return {
        "total": projects.count(),
        "active": projects.filter(status="active").count(),
        "completed": projects.filter(status="completed").count(),
    }

def get_task_summary(user):
    tasks = Task.objects.filter(assigned_to=user)
    return {
        "total": tasks.count(),
        "completed": tasks.filter(is_completed=True).count(),
        "overdue": tasks.filter(is_completed=False, due_date__lt=timezone.now()).count()
    }

def get_finance_summary(user):
    income = Transaction.objects.filter(type="income").aggregate(total=models.Sum("amount"))["total"] or 0
    expense = Transaction.objects.filter(type="expense").aggregate(total=models.Sum("amount"))["total"] or 0
    goals = Goal.objects.filter(owner=user)
    return {
        "income": income,
        "expenses": expense,
        "goals_count": goals.count(),
    }

def get_field_summary(user):
    visits = FieldVisit.objects.all()
    return {
        "total_visits": visits.count(),
        "recent": visits.order_by("-date")[:5].values("location", "visited_by__email", "date")
    }

def get_leads_summary(user):
    return {
        "leads_total": Lead.objects.count(),
        "converted": Lead.objects.filter(status="converted").count(),
        "pending": Lead.objects.filter(status="pending").count()
    }

def get_social_summary(user):
    posts = SocialPost.objects.all()
    return {
        "scheduled": posts.filter(status="scheduled").count(),
        "published": posts.filter(status="published").count(),
        "platforms": posts.values_list("platform", flat=True).distinct()
    }