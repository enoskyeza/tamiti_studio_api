from django.test import TestCase

from notifications.models import Notification
from users.models import User


class NotificationModelTests(TestCase):
    def test_create_notification(self):
        recipient = User.objects.create(username='rec', email='rec@example.com')
        notification = Notification.objects.create(recipient=recipient, verb='test')
        self.assertEqual(notification.recipient, recipient)
        self.assertFalse(notification.is_read)
