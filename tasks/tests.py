import pytest

from notifications.models import Notification
from tests.factories import TaskFactory, UserFactory


@pytest.mark.django_db
def test_task_creation_triggers_notification():
    user = UserFactory()
    TaskFactory(assigned_to=user)
    assert Notification.objects.filter(user=user).count() == 1
