import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from tests.factories import UserFactory
from .models import Notification


@pytest.mark.django_db
class TestNotificationAPI:
    def setup_method(self):
        self.client = APIClient()

    def test_auth_required(self):
        url = reverse("notification-list")
        response = self.client.get(url)
        assert response.status_code == 401

    def test_user_cannot_access_others_notifications(self):
        user1 = UserFactory()
        user2 = UserFactory()
        note = Notification.objects.create(user=user1, content="hello")

        self.client.force_authenticate(user=user2)
        url = reverse("notification-detail", args=[note.id])
        response = self.client.get(url)
        assert response.status_code == 404

    def test_mark_all_read_isolated(self):
        user1 = UserFactory()
        user2 = UserFactory()
        n1 = Notification.objects.create(user=user1, content="u1")
        n2 = Notification.objects.create(user=user2, content="u2")

        self.client.force_authenticate(user=user1)
        url = reverse("notification-mark-all-read")
        response = self.client.post(url)
        assert response.status_code == 200

        n1.refresh_from_db()
        n2.refresh_from_db()
        assert n1.read is True
        assert n2.read is False
