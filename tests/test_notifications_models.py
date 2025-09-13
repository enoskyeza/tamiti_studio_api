# tests/test_notifications_models.py
import pytest
from django.contrib.contenttypes.models import ContentType

from notifications.models import Notification
from projects.models import Project
from tests.factories import UserFactory, ProjectFactory


@pytest.mark.django_db
class TestNotificationModels:

    def test_notification_creation_and_str(self):
        """Test Notification model creation and string representation"""
        actor = UserFactory()
        recipient = UserFactory()
        project = ProjectFactory()
        
        notification = Notification.objects.create(
            actor=actor,
            recipient=recipient,
            verb="created",
            content_type=ContentType.objects.get_for_model(Project),
            object_id=project.id,
            url=f"/projects/{project.id}/",
            is_read=False
        )
        
        assert str(notification) == f"{actor} created {project}"
        assert notification.actor == actor
        assert notification.recipient == recipient
        assert notification.verb == "created"
        assert notification.target == project
        assert notification.url == f"/projects/{project.id}/"
        assert notification.is_read is False

    def test_notification_without_actor(self):
        """Test Notification can be created without actor (system notification)"""
        recipient = UserFactory()
        project = ProjectFactory()
        
        notification = Notification.objects.create(
            actor=None,
            recipient=recipient,
            verb="was updated",
            content_type=ContentType.objects.get_for_model(Project),
            object_id=project.id
        )
        
        assert notification.actor is None
        assert notification.recipient == recipient
        assert str(notification) == f"None was updated {project}"

    def test_notification_without_target(self):
        """Test Notification can be created without target object"""
        actor = UserFactory()
        recipient = UserFactory()
        
        notification = Notification.objects.create(
            actor=actor,
            recipient=recipient,
            verb="sent you a message",
            content_type=None,
            object_id=None
        )
        
        assert notification.target is None
        assert str(notification) == f"{actor} sent you a message None"

    def test_notification_generic_foreign_key(self):
        """Test Notification generic foreign key works with different models"""
        actor = UserFactory()
        recipient = UserFactory()
        project = ProjectFactory()
        
        notification = Notification.objects.create(
            actor=actor,
            recipient=recipient,
            verb="commented on",
            content_type=ContentType.objects.get_for_model(Project),
            object_id=project.id
        )
        
        # Test that target returns the correct object
        assert notification.target == project
        assert isinstance(notification.target, Project)

    def test_notification_is_read_default(self):
        """Test Notification is_read defaults to False"""
        actor = UserFactory()
        recipient = UserFactory()
        
        notification = Notification.objects.create(
            actor=actor,
            recipient=recipient,
            verb="mentioned you"
        )
        
        assert notification.is_read is False

    def test_notification_mark_as_read(self):
        """Test marking notification as read"""
        actor = UserFactory()
        recipient = UserFactory()
        
        notification = Notification.objects.create(
            actor=actor,
            recipient=recipient,
            verb="assigned you a task"
        )
        
        # Initially unread
        assert notification.is_read is False
        
        # Mark as read
        notification.is_read = True
        notification.save()
        
        # Verify it's marked as read
        notification.refresh_from_db()
        assert notification.is_read is True

    def test_notification_ordering(self):
        """Test Notification ordering by created_at descending"""
        actor = UserFactory()
        recipient = UserFactory()
        
        # Create notifications in sequence
        notif1 = Notification.objects.create(
            actor=actor,
            recipient=recipient,
            verb="first notification"
        )
        
        notif2 = Notification.objects.create(
            actor=actor,
            recipient=recipient,
            verb="second notification"
        )
        
        notif3 = Notification.objects.create(
            actor=actor,
            recipient=recipient,
            verb="third notification"
        )
        
        # Get all notifications - should be ordered by created_at desc
        notifications = list(Notification.objects.all())
        
        # Most recent should be first
        assert notifications[0] == notif3
        assert notifications[1] == notif2
        assert notifications[2] == notif1

    def test_notification_indexes(self):
        """Test that notification model has proper database indexes"""
        # This test verifies the indexes are defined in Meta
        meta = Notification._meta
        indexes = meta.indexes
        
        # Should have indexes on recipient, is_read, and created_at
        index_fields = []
        for index in indexes:
            index_fields.extend(index.fields)
        
        assert 'recipient' in index_fields
        assert 'is_read' in index_fields
        assert 'created_at' in index_fields

    def test_notification_recipient_cascade_delete(self):
        """Test notification is deleted when recipient is deleted"""
        actor = UserFactory()
        recipient = UserFactory()
        
        notification = Notification.objects.create(
            actor=actor,
            recipient=recipient,
            verb="test notification"
        )
        notification_id = notification.id
        
        # Delete recipient
        recipient.delete()
        
        # Notification should be deleted
        assert not Notification.objects.filter(id=notification_id).exists()

    def test_notification_actor_set_null_on_delete(self):
        """Test notification actor is set to null when actor is deleted"""
        actor = UserFactory()
        recipient = UserFactory()
        
        notification = Notification.objects.create(
            actor=actor,
            recipient=recipient,
            verb="test notification"
        )
        
        # Delete actor
        actor.delete()
        notification.refresh_from_db()
        
        # Notification should still exist but actor should be null
        assert notification.actor is None
        assert notification.recipient == recipient

    def test_notification_content_type_cascade_delete(self):
        """Test notification is deleted when content_type is deleted"""
        actor = UserFactory()
        recipient = UserFactory()
        project = ProjectFactory()
        content_type = ContentType.objects.get_for_model(Project)
        
        notification = Notification.objects.create(
            actor=actor,
            recipient=recipient,
            verb="test notification",
            content_type=content_type,
            object_id=project.id
        )
        notification_id = notification.id
        
        # Delete content type (this is unlikely in practice but tests the constraint)
        content_type.delete()
        
        # Notification should be deleted
        assert not Notification.objects.filter(id=notification_id).exists()

    def test_notification_with_url(self):
        """Test notification with URL field"""
        actor = UserFactory()
        recipient = UserFactory()
        
        notification = Notification.objects.create(
            actor=actor,
            recipient=recipient,
            verb="invited you to",
            url="/projects/123/invite/"
        )
        
        assert notification.url == "/projects/123/invite/"

    def test_notification_without_url(self):
        """Test notification without URL (blank/null)"""
        actor = UserFactory()
        recipient = UserFactory()
        
        notification = Notification.objects.create(
            actor=actor,
            recipient=recipient,
            verb="general notification"
        )
        
        assert notification.url == "" or notification.url is None

    def test_base_model_inheritance(self):
        """Test Notification inherits BaseModel functionality"""
        actor = UserFactory()
        recipient = UserFactory()
        
        notification = Notification.objects.create(
            actor=actor,
            recipient=recipient,
            verb="inheritance test"
        )
        
        # Check BaseModel fields
        assert hasattr(notification, 'created_at')
        assert hasattr(notification, 'updated_at')
        assert hasattr(notification, 'deleted_at')
        assert hasattr(notification, 'is_deleted')
        assert hasattr(notification, 'uuid')
        
        # Check soft delete method
        assert hasattr(notification, 'soft_delete')
        
        # Test soft delete functionality
        notification.soft_delete()
        assert notification.is_deleted is True
        assert notification.deleted_at is not None

    def test_notification_recipient_related_name(self):
        """Test recipient related name works correctly"""
        actor = UserFactory()
        recipient = UserFactory()
        
        notif1 = Notification.objects.create(
            actor=actor,
            recipient=recipient,
            verb="first notification"
        )
        
        notif2 = Notification.objects.create(
            actor=actor,
            recipient=recipient,
            verb="second notification"
        )
        
        # Test reverse relationship
        user_notifications = recipient.notifications.all()
        assert notif1 in user_notifications
        assert notif2 in user_notifications
        assert user_notifications.count() == 2

    def test_notification_actor_related_name(self):
        """Test actor related name works correctly"""
        actor = UserFactory()
        recipient1 = UserFactory()
        recipient2 = UserFactory()
        
        notif1 = Notification.objects.create(
            actor=actor,
            recipient=recipient1,
            verb="notification to user 1"
        )
        
        notif2 = Notification.objects.create(
            actor=actor,
            recipient=recipient2,
            verb="notification to user 2"
        )
        
        # Test reverse relationship for actor
        actor_notifications = actor.actor_notifications.all()
        assert notif1 in actor_notifications
        assert notif2 in actor_notifications
        assert actor_notifications.count() == 2
