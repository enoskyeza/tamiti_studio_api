
import pytest
from rest_framework.test import APIClient
from django.urls import reverse
from social.models import SocialPost
from .factories import UserFactory

pytestmark = pytest.mark.django_db


def test_create_social_post():
    client = APIClient()
    user = UserFactory()
    client.force_authenticate(user=user)

    data = {
        "title": "Launch Day",
        "content_text": "We're going live!",
        "platform": "facebook",
        "scheduled_for": "2030-01-01T10:00:00Z",
        "status": "draft",
    }

    response = client.post(reverse("socialpost-list"), data)
    assert response.status_code == 201
    assert SocialPost.objects.filter(title="Launch Day").exists()
