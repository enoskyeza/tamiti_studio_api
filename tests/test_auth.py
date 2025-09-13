# tests/test_auth.py
import pytest
from django.urls import reverse
from users.models import User
from tests.factories import UserFactory
from rest_framework.test import APIClient
from users.tokens import account_activation_token, encode_uid

@pytest.mark.django_db
class TestAuthEndpoints:

    def setup_method(self):
        self.client = APIClient()

    def test_register_user(self):
        data = {
            "username": "newuser",
            "email": "new@example.com",
            "phone": "0700123456",
            "password": "securepass123"
        }
        response = self.client.post(reverse('register'), data)
        assert response.status_code == 201
        assert User.objects.filter(email="new@example.com").exists()

    def test_login_user(self):
        user = UserFactory()
        response = self.client.post(reverse('login'), {
            "username": user.username,
            "password": "testpass123"
        })
        assert response.status_code == 200
        # The response contains access token with key 'access'
        assert "access" in response.data

    def test_verify_email(self):
        user = UserFactory(is_verified=False)
        uid = encode_uid(user)
        token = account_activation_token.make_token(user)

        response = self.client.get(reverse('verify-email'), {"uid": uid, "token": token})
        assert response.status_code == 200
        user.refresh_from_db()
        assert user.is_verified is True

    def test_password_reset_flow(self):
        user = UserFactory()
        # Step 1: Request reset
        response = self.client.post(reverse('password-reset-request'), {
            "email": user.email
        })
        assert response.status_code == 200

        # Step 2: Confirm reset
        uid = encode_uid(user)
        token = account_activation_token.make_token(user)
        response = self.client.post(reverse('password-reset-confirm'), {
            "uid": uid,
            "token": token,
            "new_password": "newsecure123"
        })
        assert response.status_code == 200

        # Confirm login with new password
        response = self.client.post(reverse('login'), {
            "username": user.username,
            "password": "newsecure123"
        })
        assert response.status_code == 200
