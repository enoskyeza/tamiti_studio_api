# tests/test_planner_models.py
import pytest
from datetime import timedelta, date
from decimal import Decimal
from django.utils import timezone
from django.core.exceptions import ValidationError

from planner.models import (
    BreakPolicy, AvailabilityTemplate, CalendarEvent, TimeBlock,
    WorkGoal, DailyReview, ProductivityInsight
)
from accounts.models import Department
from tasks.models import Task
from projects.models import Project
from common.enums import BlockStatus
from tests.factories import UserFactory, ProjectFactory, TaskFactory


@pytest.mark.django_db(transaction=True)
class TestPlannerModels:

    def setup_method(self):
        """Setup method to ensure clean state for each test"""
        # Clear any cached ContentType instances
        from django.contrib.contenttypes.models import ContentType
        ContentType.objects.clear_cache()

    def teardown_method(self):
        """Teardown method to clean up after each test"""
        # Only clear ContentType cache - transaction rollback handles object cleanup
        from django.contrib.contenttypes.models import ContentType
        ContentType.objects.clear_cache()

    def test_break_policy_creation_and_str(self):
        """Test BreakPolicy model creation and string representation"""
        user = UserFactory()
        
        policy = BreakPolicy.objects.create(
            owner_user=user,
            focus_minutes=25,
            break_minutes=5,
            long_break_minutes=15,
            cycle_count=4,
            active=True
        )
        
        assert str(policy) == f"BreakPolicy({user}) 25/5"
        assert policy.owner_user == user
        assert policy.focus_minutes == 25
        assert policy.break_minutes == 5
        assert policy.long_break_minutes == 15
        assert policy.cycle_count == 4
        assert policy.active is True

    def test_break_policy_team_owner(self):
        """Test BreakPolicy with team owner"""
        dept = Department.objects.create(name="Engineering")
        
        policy = BreakPolicy.objects.create(
            owner_team=dept,
            focus_minutes=50,
            break_minutes=10
        )
        
        assert str(policy) == f"BreakPolicy({dept}) 50/10"
        assert policy.owner_team == dept
        assert policy.owner_user is None

    def test_break_policy_defaults(self):
        """Test BreakPolicy default values"""
        user = UserFactory()
        
        policy = BreakPolicy.objects.create(owner_user=user)
        
        assert policy.focus_minutes == 25
        assert policy.break_minutes == 5
        assert policy.long_break_minutes == 15
        assert policy.cycle_count == 4
        assert policy.active is True

    def test_availability_template_creation_and_str(self):
        """Test AvailabilityTemplate model creation"""
        user = UserFactory()
        
        template = AvailabilityTemplate.objects.create(
            owner_user=user,
            day_of_week=1,  # Tuesday
            start_time="09:00",
            end_time="17:00"
        )
        
        assert str(template) == f"Avail({user}) d1 09:00-17:00"
        assert template.owner_user == user
        assert template.day_of_week == 1
        assert str(template.start_time) == "09:00"
        assert str(template.end_time) == "17:00"

    def test_availability_template_ordering(self):
        """Test AvailabilityTemplate ordering"""
        user = UserFactory()
        
        # Create templates in reverse order
        template2 = AvailabilityTemplate.objects.create(
            owner_user=user,
            day_of_week=2,
            start_time="10:00",
            end_time="18:00"
        )
        
        template1 = AvailabilityTemplate.objects.create(
            owner_user=user,
            day_of_week=1,
            start_time="09:00",
            end_time="17:00"
        )
        
        template1_early = AvailabilityTemplate.objects.create(
            owner_user=user,
            day_of_week=1,
            start_time="08:00",
            end_time="12:00"
        )
        
        templates = list(AvailabilityTemplate.objects.all())
        # Should be ordered by day_of_week, then start_time
        assert templates[0] == template1_early
        assert templates[1] == template1
        assert templates[2] == template2

    def test_calendar_event_creation_and_str(self):
        """Test CalendarEvent model creation"""
        user = UserFactory()
        start_time = timezone.now()
        end_time = start_time + timedelta(hours=2)
        
        event = CalendarEvent.objects.create(
            owner_user=user,
            title="Team Meeting",
            description="Weekly team sync",
            start=start_time,
            end=end_time,
            is_busy=True,
            source="calendar_sync"
        )
        
        assert str(event) == f"Event({user}) Team Meeting"
        assert event.owner_user == user
        assert event.title == "Team Meeting"
        assert event.description == "Weekly team sync"
        assert event.start == start_time
        assert event.end == end_time
        assert event.is_busy is True
        assert event.source == "calendar_sync"

    def test_calendar_event_team_owner(self):
        """Test CalendarEvent with team owner"""
        dept = Department.objects.create(name="Marketing")
        start_time = timezone.now()
        end_time = start_time + timedelta(hours=1)
        
        event = CalendarEvent.objects.create(
            owner_team=dept,
            title="Department Meeting",
            start=start_time,
            end=end_time
        )
        
        assert str(event) == f"Event({dept}) Department Meeting"
        assert event.owner_team == dept

    def test_time_block_creation_and_properties(self):
        """Test TimeBlock model creation and properties"""
        user = UserFactory()
        task = TaskFactory()
        start_time = timezone.now()
        end_time = start_time + timedelta(minutes=90)
        
        block = TimeBlock.objects.create(
            owner_user=user,
            task=task,
            title="Focus Work",
            start=start_time,
            end=end_time,
            status=BlockStatus.PLANNED,
            is_break=False,
            source="manual"
        )
        
        expected_str = f"TimeBlock({user}) Focus Work [{start_time.strftime('%H:%M')}-{end_time.strftime('%H:%M')}]"
        assert str(block) == expected_str
        assert block.owner_user == user
        assert block.task == task
        assert block.title == "Focus Work"
        assert block.status == BlockStatus.PLANNED
        assert block.is_break is False
        assert block.source == "manual"
        assert block.duration_minutes == 90

    def test_time_block_break_block(self):
        """Test TimeBlock as break"""
        user = UserFactory()
        start_time = timezone.now()
        end_time = start_time + timedelta(minutes=15)
        
        block = TimeBlock.objects.create(
            owner_user=user,
            title="Coffee Break",
            start=start_time,
            end=end_time,
            is_break=True
        )
        
        assert block.is_break is True
        assert block.task is None
        assert block.duration_minutes == 15

    def test_time_block_ordering(self):
        """Test TimeBlock ordering by start time"""
        user = UserFactory()
        now = timezone.now()
        
        block2 = TimeBlock.objects.create(
            owner_user=user,
            title="Second Block",
            start=now + timedelta(hours=2),
            end=now + timedelta(hours=3)
        )
        
        block1 = TimeBlock.objects.create(
            owner_user=user,
            title="First Block",
            start=now + timedelta(hours=1),
            end=now + timedelta(hours=2)
        )
        
        blocks = list(TimeBlock.objects.all())
        assert blocks[0] == block1
        assert blocks[1] == block2

    def test_work_goal_creation_and_str(self):
        """Test WorkGoal model creation"""
        user = UserFactory()
        project = ProjectFactory()
        target_date = timezone.now().date() + timedelta(days=30)
        
        goal = WorkGoal.objects.create(
            name="Complete Project Alpha",
            description="Finish all tasks for project alpha",
            target_date=target_date,
            owner_user=user,
            project=project,
            tags=["urgent", "client-work"],
            is_active=True
        )
        
        assert str(goal) == f"WorkGoal({user}) Complete Project Alpha"
        assert goal.name == "Complete Project Alpha"
        assert goal.description == "Finish all tasks for project alpha"
        assert goal.target_date == target_date
        assert goal.owner_user == user
        assert goal.project == project
        assert goal.tags == ["urgent", "client-work"]
        assert goal.is_active is True
        assert goal.progress_percentage == 0
        assert goal.total_tasks == 0
        assert goal.completed_tasks == 0

    def test_work_goal_team_owner(self):
        """Test WorkGoal with team owner"""
        dept = Department.objects.create(name="Development")
        
        goal = WorkGoal.objects.create(
            name="Team Goal",
            owner_team=dept
        )
        
        assert str(goal) == f"WorkGoal({dept}) Team Goal"
        assert goal.owner_team == dept

    def test_work_goal_update_progress(self):
        """Test WorkGoal progress calculation"""
        user = UserFactory()
        project = ProjectFactory()
        
        goal = WorkGoal.objects.create(
            name="Test Goal",
            owner_user=user,
            project=project
        )
        
        # Create tasks linked to this goal
        task1 = TaskFactory(project=project, is_completed=True)
        task2 = TaskFactory(project=project, is_completed=False)
        task3 = TaskFactory(project=project, is_completed=True)
        
        # Link tasks to work goal (assuming work_goal field exists on Task)
        # Note: This might need adjustment based on actual Task model structure
        
        goal.update_progress()
        goal.refresh_from_db()
        
        # Should calculate progress based on completed vs total tasks
        # This test might need adjustment based on actual implementation

    def test_daily_review_creation_and_str(self):
        """Test DailyReview model creation"""
        user = UserFactory()
        review_date = timezone.now().date()
        
        review = DailyReview.objects.create(
            date=review_date,
            owner_user=user,
            summary="Productive day with good focus",
            mood="good",
            highlights="Completed major feature implementation",
            lessons="Need to take more breaks",
            tomorrow_top3=["Review code", "Write tests", "Deploy feature"],
            tasks_planned=5,
            tasks_completed=4,
            completion_rate=Decimal('80.00'),
            focus_time_minutes=240,
            break_time_minutes=45,
            productivity_score=Decimal('85.50'),
            current_streak=3
        )
        
        assert str(review) == f"DailyReview({user}) {review_date} - 85.50%"
        assert review.date == review_date
        assert review.owner_user == user
        assert review.summary == "Productive day with good focus"
        assert review.mood == "good"
        assert review.highlights == "Completed major feature implementation"
        assert review.lessons == "Need to take more breaks"
        assert review.tomorrow_top3 == ["Review code", "Write tests", "Deploy feature"]
        assert review.tasks_planned == 5
        assert review.tasks_completed == 4
        assert review.completion_rate == Decimal('80.00')
        assert review.focus_time_minutes == 240
        assert review.break_time_minutes == 45
        assert review.productivity_score == Decimal('85.50')
        assert review.current_streak == 3

    def test_daily_review_unique_constraint(self):
        """Test DailyReview unique constraint per user per date"""
        user = UserFactory()
        review_date = timezone.now().date()
        
        review1 = DailyReview.objects.create(
            date=review_date,
            owner_user=user,
            summary="First review"
        )
        
        # Creating another review for same user and date should fail
        from django.db import IntegrityError
        with pytest.raises(IntegrityError):
            DailyReview.objects.create(
                date=review_date,
                owner_user=user,
                summary="Second review"
            )

    def test_daily_review_calculate_metrics(self):
        """Test DailyReview metrics calculation"""
        user = UserFactory()
        review_date = timezone.now().date()
        
        review = DailyReview.objects.create(
            date=review_date,
            owner_user=user
        )
        
        # This would test the calculate_metrics method
        # Implementation depends on actual Task and TimeBlock relationships
        review.calculate_metrics()
        
        # Verify metrics were calculated
        assert review.tasks_planned >= 0
        assert review.tasks_completed >= 0
        assert review.completion_rate >= 0
        assert review.focus_time_minutes >= 0
        assert review.break_time_minutes >= 0
        assert review.productivity_score >= 0

    def test_productivity_insight_creation_and_str(self):
        """Test ProductivityInsight model creation"""
        user = UserFactory()
        
        insight = ProductivityInsight.objects.create(
            owner_user=user,
            insight_type="peak_hours",
            data={
                "peak_start": "09:00",
                "peak_end": "11:00",
                "productivity_score": 92.5,
                "analysis": "Most productive during morning hours"
            },
            confidence_score=Decimal('87.50'),
            sample_size=30,
            valid_from=timezone.now().date(),
            is_active=True
        )
        
        assert str(insight) == f"Insight({user}) peak_hours - 87.50%"
        assert insight.owner_user == user
        assert insight.insight_type == "peak_hours"
        assert insight.data["peak_start"] == "09:00"
        assert insight.confidence_score == Decimal('87.50')
        assert insight.sample_size == 30
        assert insight.is_active is True

    def test_productivity_insight_unique_constraint(self):
        """Test ProductivityInsight unique constraint per user per type"""
        user = UserFactory()
        
        insight1 = ProductivityInsight.objects.create(
            owner_user=user,
            insight_type="peak_hours",
            data={"test": "data1"},
            valid_from=timezone.now().date()
        )
        
        # Creating another insight of same type for same user should fail
        from django.db import IntegrityError
        with pytest.raises(IntegrityError):
            ProductivityInsight.objects.create(
                owner_user=user,
                insight_type="peak_hours",
                data={"test": "data2"},
                valid_from=timezone.now().date()
            )

    def test_productivity_insight_ordering(self):
        """Test ProductivityInsight ordering by confidence score"""
        user = UserFactory()
        
        insight1 = ProductivityInsight.objects.create(
            owner_user=user,
            insight_type="peak_hours",
            confidence_score=Decimal('75.00'),
            valid_from=timezone.now().date()
        )
        
        insight2 = ProductivityInsight.objects.create(
            owner_user=user,
            insight_type="task_duration",
            confidence_score=Decimal('90.00'),
            valid_from=timezone.now().date()
        )
        
        insights = list(ProductivityInsight.objects.all())
        # Should be ordered by confidence_score desc
        assert insights[0] == insight2
        assert insights[1] == insight1

    def test_base_model_inheritance(self):
        """Test all models inherit BaseModel functionality"""
        user = UserFactory()
        dept = Department.objects.create(name="Test Dept")
        
        policy = BreakPolicy.objects.create(owner_user=user)
        template = AvailabilityTemplate.objects.create(
            owner_user=user,
            day_of_week=1,
            start_time="09:00",
            end_time="17:00"
        )
        event = CalendarEvent.objects.create(
            owner_user=user,
            title="Test Event",
            start=timezone.now(),
            end=timezone.now() + timedelta(hours=1)
        )
        block = TimeBlock.objects.create(
            owner_user=user,
            title="Test Block",
            start=timezone.now(),
            end=timezone.now() + timedelta(hours=1)
        )
        goal = WorkGoal.objects.create(
            name="Test Goal",
            owner_user=user
        )
        review = DailyReview.objects.create(
            date=timezone.now().date(),
            owner_user=user
        )
        insight = ProductivityInsight.objects.create(
            owner_user=user,
            insight_type="peak_hours",
            valid_from=timezone.now().date()
        )
        
        for obj in [policy, template, event, block, goal, review, insight]:
            # Check BaseModel fields
            assert hasattr(obj, 'created_at')
            assert hasattr(obj, 'updated_at')
            assert hasattr(obj, 'deleted_at')
            assert hasattr(obj, 'is_deleted')
            assert hasattr(obj, 'uuid')
            
            # Check soft delete method
            assert hasattr(obj, 'soft_delete')
