import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from common.enums import LeadStage, PostStatus, ProjectStatus, TransactionType
from tests.factories import (
    GoalFactory,
    LeadFactory,
    ProjectFactory,
    SocialPostFactory,
    TaskFactory,
    TransactionFactory,
    UserFactory,
    VisitFactory,
)


@pytest.mark.django_db
def test_dashboard_kpis_endpoint_returns_metrics():
    user = UserFactory()

    # projects
    ProjectFactory(created_by=user, status=ProjectStatus.ACTIVE)
    ProjectFactory(created_by=user, status=ProjectStatus.COMPLETE)

    # tasks
    TaskFactory(assigned_to=user, is_completed=True)
    TaskFactory(
        assigned_to=user,
        due_date=timezone.now() - timezone.timedelta(days=1),
    )

    # finance
    TransactionFactory(type=TransactionType.INCOME, amount=100, account=None)
    TransactionFactory(type=TransactionType.EXPENSE, amount=50, account=None)
    GoalFactory(owner=user)

    # field and leads
    VisitFactory(rep=user)
    LeadFactory(assigned_rep=user, stage=LeadStage.WON)
    LeadFactory(assigned_rep=user, stage=LeadStage.LOST)

    # social posts
    SocialPostFactory(assigned_to=user, status=PostStatus.DRAFT)
    SocialPostFactory(assigned_to=user, status=PostStatus.PUBLISHED)

    client = APIClient()
    client.force_authenticate(user=user)

    response = client.get("/api/dashboard/kpis/")
    assert response.status_code == 200

    data = response.json()
    assert data["projects"]["total"] == 2
    assert data["projects"]["active"] == 1
    assert data["projects"]["completed"] == 1
    assert data["tasks"]["total"] == 2
    assert data["finance"]["goals_count"] == 1
    assert data["field"]["total_visits"] == 1
    assert data["leads"]["total"] == 2
    assert data["social"]["draft"] == 1
    assert data["social"]["published"] == 1

