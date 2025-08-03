"""Scheduled tasks for dashboard metrics."""

from django.contrib.auth import get_user_model
from django.core.cache import cache

from .services import get_dashboard_metrics


def cache_all_dashboard_metrics(timeout: int = 300):
    """Pre-compute dashboard metrics for all users.

    This function can be scheduled via Celery beat or a cron job to update
    cached KPIs periodically.
    """

    User = get_user_model()
    for user in User.objects.all():
        cache_key = f"dashboard:kpis:{user.pk}"
        cache.set(cache_key, get_dashboard_metrics(user), timeout)

