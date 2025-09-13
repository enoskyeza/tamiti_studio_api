# tests/test_dashboard_models.py
import pytest
from django.db import IntegrityError

from dashboard.models import DashboardWidget
from tests.factories import UserFactory


@pytest.mark.django_db
class TestDashboardModels:

    def test_dashboard_widget_creation_and_str(self):
        """Test DashboardWidget model creation and string representation"""
        user = UserFactory()
        
        widget = DashboardWidget.objects.create(
            user=user,
            name="Task Summary",
            position=1,
            is_active=True
        )
        
        assert str(widget) == f"{user.email} - Task Summary"
        assert widget.user == user
        assert widget.name == "Task Summary"
        assert widget.position == 1
        assert widget.is_active is True

    def test_dashboard_widget_defaults(self):
        """Test DashboardWidget default values"""
        user = UserFactory()
        
        widget = DashboardWidget.objects.create(
            user=user,
            name="Default Widget"
        )
        
        assert widget.position == 0
        assert widget.is_active is True

    def test_dashboard_widget_ordering(self):
        """Test DashboardWidget ordering by position"""
        user = UserFactory()
        
        widget3 = DashboardWidget.objects.create(
            user=user,
            name="Third Widget",
            position=3
        )
        
        widget1 = DashboardWidget.objects.create(
            user=user,
            name="First Widget", 
            position=1
        )
        
        widget2 = DashboardWidget.objects.create(
            user=user,
            name="Second Widget",
            position=2
        )
        
        widgets = list(DashboardWidget.objects.all())
        assert widgets[0] == widget1
        assert widgets[1] == widget2
        assert widgets[2] == widget3

    def test_dashboard_widget_cascade_on_user_delete(self):
        """Test DashboardWidget is deleted when user is deleted"""
        user = UserFactory()
        
        widget = DashboardWidget.objects.create(
            user=user,
            name="Test Widget"
        )
        widget_id = widget.id
        
        user.delete()
        assert not DashboardWidget.objects.filter(id=widget_id).exists()

    def test_dashboard_widget_inactive(self):
        """Test DashboardWidget can be inactive"""
        user = UserFactory()
        
        widget = DashboardWidget.objects.create(
            user=user,
            name="Inactive Widget",
            is_active=False
        )
        
        assert widget.is_active is False

    def test_multiple_widgets_per_user(self):
        """Test user can have multiple dashboard widgets"""
        user = UserFactory()
        
        widget1 = DashboardWidget.objects.create(
            user=user,
            name="Widget 1",
            position=1
        )
        
        widget2 = DashboardWidget.objects.create(
            user=user,
            name="Widget 2", 
            position=2
        )
        
        user_widgets = user.dashboard_widgets.all()
        assert widget1 in user_widgets
        assert widget2 in user_widgets
        assert user_widgets.count() == 2

    def test_dashboard_widget_position_can_be_same(self):
        """Test multiple widgets can have same position (no unique constraint)"""
        user = UserFactory()
        
        widget1 = DashboardWidget.objects.create(
            user=user,
            name="Widget 1",
            position=1
        )
        
        widget2 = DashboardWidget.objects.create(
            user=user,
            name="Widget 2",
            position=1  # Same position is allowed
        )
        
        assert widget1.position == widget2.position == 1

    def test_dashboard_widget_different_users(self):
        """Test widgets for different users are independent"""
        user1 = UserFactory()
        user2 = UserFactory()
        
        widget1 = DashboardWidget.objects.create(
            user=user1,
            name="User 1 Widget"
        )
        
        widget2 = DashboardWidget.objects.create(
            user=user2,
            name="User 2 Widget"
        )
        
        assert user1.dashboard_widgets.count() == 1
        assert user2.dashboard_widgets.count() == 1
        assert widget1 not in user2.dashboard_widgets.all()
        assert widget2 not in user1.dashboard_widgets.all()
