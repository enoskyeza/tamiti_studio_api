"""Utilities for collecting dashboard metrics."""

from django.core.cache import cache
from django.db import models
from django.utils import timezone

from common.enums import (
    LeadStage,
    PostStatus,
    ProjectStatus,
    TransactionType,
)
from finance.models import Goal, Transaction
from field.models import Lead, Visit
from projects.models import Project
from social.models import SocialPost
from tasks.models import Task


def get_project_summary(user):
    """Return a summary of the user's projects."""
    projects = Project.objects.filter(created_by=user)
    return {
        "total": projects.count(),
        "active": projects.filter(status=ProjectStatus.ACTIVE).count(),
        "completed": projects.filter(status=ProjectStatus.COMPLETE).count(),
    }


def get_task_summary(user):
    """Return task statistics for the user."""
    tasks = Task.objects.filter(assigned_to=user)
    return {
        "total": tasks.count(),
        "completed": tasks.filter(is_completed=True).count(),
        "overdue": tasks.filter(
            is_completed=False, due_date__lt=timezone.now()
        ).count(),
    }


def get_finance_summary(user):
    """Aggregate basic financial information."""
    income = (
        Transaction.objects.filter(type=TransactionType.INCOME)
        .aggregate(total=models.Sum("amount"))
        .get("total")
        or 0
    )
    expense = (
        Transaction.objects.filter(type=TransactionType.EXPENSE)
        .aggregate(total=models.Sum("amount"))
        .get("total")
        or 0
    )
    goals = Goal.objects.filter(owner=user)
    return {
        "income": income,
        "expenses": expense,
        "goals_count": goals.count(),
    }


def get_field_summary(user):
    """Return visit information for the user."""
    visits = Visit.objects.filter(rep=user)
    return {
        "total_visits": visits.count(),
        "recent": list(
            visits.order_by("-date_time")[:5].values(
                "location", "rep__email", "date_time"
            )
        ),
    }


def get_leads_summary(user):
    """Return lead statistics for the user."""
    leads = Lead.objects.filter(assigned_rep=user)
    return {
        "total": leads.count(),
        "won": leads.filter(stage=LeadStage.WON).count(),
        "lost": leads.filter(stage=LeadStage.LOST).count(),
    }


def get_social_summary(user):
    """Return social media post statistics for the user."""
    posts = SocialPost.objects.filter(assigned_to=user)
    return {
        "draft": posts.filter(status=PostStatus.DRAFT).count(),
        "published": posts.filter(status=PostStatus.PUBLISHED).count(),
        "platforms": list(posts.values_list("platform", flat=True).distinct()),
    }


def get_dashboard_metrics(user):
    """Collect KPI metrics from all modules for ``user``."""
    return {
        "projects": get_project_summary(user),
        "tasks": get_task_summary(user),
        "finance": get_finance_summary(user),
        "field": get_field_summary(user),
        "leads": get_leads_summary(user),
        "social": get_social_summary(user),
    }


def get_cached_dashboard_metrics(user, timeout: int = 300):
    """Return cached dashboard metrics for ``user``.

    Expensive metrics can be pre-computed and cached by a scheduled task
    (Celery beat or a cron job) to speed up API responses.
    """

    cache_key = f"dashboard:kpis:{user.pk}"
    data = cache.get(cache_key)
    if data is None:
        data = get_dashboard_metrics(user)
        cache.set(cache_key, data, timeout)
    return data

