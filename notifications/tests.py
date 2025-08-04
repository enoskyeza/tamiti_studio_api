# <<<<<<< codex/implement-notification-api-components
# import pytest
# from django.urls import reverse
# from django.utils import timezone
# from rest_framework.test import APIClient

# from users.models import User
# from .models import Notification


# @pytest.mark.django_db
# def test_list_notifications_only_for_user():
#     user = User.objects.create_user(username='u1', email='u1@example.com', password='pass')
#     other = User.objects.create_user(username='u2', email='u2@example.com', password='pass')
#     Notification.objects.create(recipient=user, actor=other, verb='test')
#     Notification.objects.create(recipient=other, actor=user, verb='other')

#     client = APIClient()
#     client.force_authenticate(user)
#     url = reverse('notification-list')
#     resp = client.get(url)
#     assert resp.status_code == 200
#     assert resp.data['count'] == 1
#     assert resp.data['results'][0]['verb'] == 'test'


# @pytest.mark.django_db
# def test_filter_notifications_by_is_read_and_timestamp():
#     user = User.objects.create_user(username='u1', email='u1@example.com', password='pass')
#     other = User.objects.create_user(username='u2', email='u2@example.com', password='pass')
#     old = Notification.objects.create(recipient=user, actor=other, verb='old', is_read=True)
#     old.timestamp = timezone.now() - timezone.timedelta(days=1)
#     old.save(update_fields=['timestamp'])
#     new = Notification.objects.create(recipient=user, actor=other, verb='new', is_read=False)

#     client = APIClient()
#     client.force_authenticate(user)
#     url = reverse('notification-list')

#     resp = client.get(url, {'is_read': False})
#     assert resp.status_code == 200
#     assert resp.data['count'] == 1
#     assert resp.data['results'][0]['verb'] == 'new'

#     cutoff = timezone.now() - timezone.timedelta(hours=1)
#     resp = client.get(url, {'timestamp__gte': cutoff.isoformat()})
#     assert resp.status_code == 200
#     assert resp.data['count'] == 1
#     assert resp.data['results'][0]['verb'] == 'new'


# @pytest.mark.django_db
# def test_mark_read_unread_and_mark_all():
#     user = User.objects.create_user(username='u1', email='u1@example.com', password='pass')
#     other = User.objects.create_user(username='u2', email='u2@example.com', password='pass')
#     n1 = Notification.objects.create(recipient=user, actor=other, verb='n1')
#     n2 = Notification.objects.create(recipient=user, actor=other, verb='n2')

#     client = APIClient()
#     client.force_authenticate(user)

#     url = reverse('notification-mark-read', args=[n1.id])
#     resp = client.post(url)
#     assert resp.status_code == 200
#     n1.refresh_from_db()
#     assert n1.is_read is True

#     url = reverse('notification-mark-unread', args=[n1.id])
#     resp = client.post(url)
#     assert resp.status_code == 200
#     n1.refresh_from_db()
#     assert n1.is_read is False

#     url = reverse('notification-mark-all-read')
#     resp = client.post(url)
#     assert resp.status_code == 200
#     assert Notification.objects.filter(recipient=user, is_read=True).count() == 2
# =======
# # <<<<<<< codex/create-notifications-app-with-notification-model
# # from django.test import TestCase

# # from notifications.models import Notification
# # from users.models import User


# # class NotificationModelTests(TestCase):
# #     def test_create_notification(self):
# #         recipient = User.objects.create(username='rec', email='rec@example.com')
# #         notification = Notification.objects.create(recipient=recipient, verb='test')
# #         self.assertEqual(notification.recipient, recipient)
# #         self.assertFalse(notification.is_read)
# # =======
# # import pytest
# # from django.urls import reverse
# # from rest_framework.test import APIClient

# # from tests.factories import UserFactory
# # from .models import Notification


# # @pytest.mark.django_db
# # class TestNotificationAPI:
# #     def setup_method(self):
# #         self.client = APIClient()

# #     def test_auth_required(self):
# #         url = reverse("notification-list")
# #         response = self.client.get(url)
# #         assert response.status_code == 401

# #     def test_user_cannot_access_others_notifications(self):
# #         user1 = UserFactory()
# #         user2 = UserFactory()
# #         note = Notification.objects.create(user=user1, content="hello")

# #         self.client.force_authenticate(user=user2)
# #         url = reverse("notification-detail", args=[note.id])
# #         response = self.client.get(url)
# #         assert response.status_code == 404

# #     def test_mark_all_read_isolated(self):
# #         user1 = UserFactory()
# #         user2 = UserFactory()
# #         n1 = Notification.objects.create(user=user1, content="u1")
# #         n2 = Notification.objects.create(user=user2, content="u2")

# #         self.client.force_authenticate(user=user1)
# #         url = reverse("notification-mark-all-read")
# #         response = self.client.post(url)
# #         assert response.status_code == 200

# #         n1.refresh_from_db()
# #         n2.refresh_from_db()
# #         assert n1.read is True
# #         assert n2.read is False
# # >>>>>>> content
# >>>>>>> content
