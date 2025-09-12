import pytest
from datetime import date, timedelta
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from tasks.models import Task, BacklogItem, TaskChecklist
from projects.models import Project
from common.enums import TaskStatus, PriorityLevel

User = get_user_model()


@pytest.mark.django_db(transaction=True)
class TestBacklogItemModel:
    """Test BacklogItem model functionality"""
    
    def setup_method(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        from datetime import date
        self.project = Project.objects.create(
            name='Test Project',
            created_by=self.user,
            start_date=date.today(),
            due_date=date.today() + timedelta(days=30)
        )
    
    def test_backlog_item_creation(self):
        """Test creating a backlog item"""
        backlog_item = BacklogItem.objects.create(
            title='Test Backlog Item',
            source=BacklogItem.Source.PERSONAL,
            created_by=self.user
        )
        
        assert backlog_item.title == 'Test Backlog Item'
        assert backlog_item.source == BacklogItem.Source.PERSONAL
        assert backlog_item.created_by == self.user
        assert not backlog_item.is_converted
        assert backlog_item.converted_to_task is None
    
    def test_backlog_item_str_representation(self):
        """Test string representation of backlog item"""
        backlog_item = BacklogItem.objects.create(
            title='Test Item',
            source=BacklogItem.Source.WORK,
            created_by=self.user
        )
        
        expected = 'Test Item (Work)'
        assert str(backlog_item) == expected
    
    def test_convert_to_task_basic(self):
        """Test converting backlog item to task"""
        backlog_item = BacklogItem.objects.create(
            title='Convert Me',
            source=BacklogItem.Source.CLIENT,
            created_by=self.user
        )
        
        task = backlog_item.convert_to_task()
        
        assert isinstance(task, Task)
        assert task.title == 'Convert Me'
        assert task.created_by == self.user
        assert task.assigned_to == self.user
        
        # Check backlog item is marked as converted
        backlog_item.refresh_from_db()
        assert backlog_item.is_converted
        assert backlog_item.converted_to_task == task
    
    def test_convert_to_task_with_additional_data(self):
        """Test converting backlog item with additional task data"""
        backlog_item = BacklogItem.objects.create(
            title='Advanced Convert',
            source=BacklogItem.Source.WORK,
            created_by=self.user
        )
        
        task_data = {
            'description': 'Detailed description',
            'priority': PriorityLevel.HIGH,
            'project': self.project,
            'estimated_hours': 5
        }
        
        task = backlog_item.convert_to_task(**task_data)
        
        assert task.title == 'Advanced Convert'
        assert task.description == 'Detailed description'
        assert task.priority == PriorityLevel.HIGH
        assert task.project == self.project
        assert task.estimated_hours == 5
    
    def test_convert_already_converted_item(self):
        """Test converting an already converted backlog item"""
        backlog_item = BacklogItem.objects.create(
            title='Already Converted',
            source=BacklogItem.Source.PERSONAL,
            created_by=self.user
        )
        
        # First conversion
        task1 = backlog_item.convert_to_task()
        
        # Second conversion should return the same task
        task2 = backlog_item.convert_to_task()
        
        assert task1 == task2
        assert backlog_item.converted_to_task == task1


@pytest.mark.django_db(transaction=True)
class TestTaskChecklistModel:
    """Test TaskChecklist model functionality"""
    
    def setup_method(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.task = Task.objects.create(
            title='Test Task',
            created_by=self.user
        )
    
    def test_checklist_creation(self):
        """Test creating a checklist item"""
        checklist_item = TaskChecklist.objects.create(
            task=self.task,
            title='Test Checklist Item',
            position=1
        )
        
        assert checklist_item.task == self.task
        assert checklist_item.title == 'Test Checklist Item'
        assert not checklist_item.is_completed
        assert checklist_item.completed_at is None
        assert checklist_item.position == 1
    
    def test_checklist_str_representation(self):
        """Test string representation of checklist item"""
        checklist_item = TaskChecklist.objects.create(
            task=self.task,
            title='Test Item'
        )
        
        assert str(checklist_item) == '○ Test Item'
        
        checklist_item.mark_completed()
        assert str(checklist_item) == '✓ Test Item'
    
    def test_mark_completed(self):
        """Test marking checklist item as completed"""
        checklist_item = TaskChecklist.objects.create(
            task=self.task,
            title='Complete Me'
        )
        
        assert not checklist_item.is_completed
        assert checklist_item.completed_at is None
        
        checklist_item.mark_completed()
        
        assert checklist_item.is_completed
        assert checklist_item.completed_at is not None
    
    def test_mark_incomplete(self):
        """Test marking checklist item as incomplete"""
        checklist_item = TaskChecklist.objects.create(
            task=self.task,
            title='Incomplete Me'
        )
        
        # First mark it as completed
        checklist_item.mark_completed()
        assert checklist_item.is_completed
        assert checklist_item.completed_at is not None
        
        # Then mark it as incomplete
        checklist_item.mark_incomplete()
        
        assert not checklist_item.is_completed
        assert checklist_item.completed_at is None
    
    def test_mark_completed_idempotent(self):
        """Test that marking already completed item doesn't change anything"""
        checklist_item = TaskChecklist.objects.create(
            task=self.task,
            title='Already Complete'
        )
        
        checklist_item.mark_completed()
        first_completed_at = checklist_item.completed_at
        
        # Mark completed again
        checklist_item.mark_completed()
        
        assert checklist_item.completed_at == first_completed_at


@pytest.mark.django_db(transaction=True)
class TestBacklogItemAPI:
    """Test BacklogItem API endpoints"""
    
    def setup_method(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='testpass123'
        )
        from datetime import date
        self.project = Project.objects.create(
            name='Test Project',
            created_by=self.user,
            start_date=date.today(),
            due_date=date.today() + timedelta(days=30)
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
    
    def test_create_backlog_item(self):
        """Test creating backlog item via API"""
        url = reverse('backlog-list')
        data = {
            'title': 'New Backlog Item',
            'source': 'work'
        }
        
        response = self.client.post(url, data)
        
        assert response.status_code == status.HTTP_201_CREATED
        assert BacklogItem.objects.count() == 1
        
        backlog_item = BacklogItem.objects.first()
        assert backlog_item.title == 'New Backlog Item'
        assert backlog_item.source == 'work'
        assert backlog_item.created_by == self.user
    
    def test_list_backlog_items(self):
        """Test listing backlog items"""
        # Create items for both users
        BacklogItem.objects.create(
            title='My Item',
            source=BacklogItem.Source.PERSONAL,
            created_by=self.user
        )
        BacklogItem.objects.create(
            title='Other Item',
            source=BacklogItem.Source.WORK,
            created_by=self.other_user
        )
        
        url = reverse('backlog-list')
        response = self.client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['title'] == 'My Item'
    
    def test_filter_by_source(self):
        """Test filtering backlog items by source"""
        BacklogItem.objects.create(
            title='Personal Item',
            source=BacklogItem.Source.PERSONAL,
            created_by=self.user
        )
        BacklogItem.objects.create(
            title='Work Item',
            source=BacklogItem.Source.WORK,
            created_by=self.user
        )
        
        url = reverse('backlog-list')
        response = self.client.get(url, {'source': 'personal'})
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['title'] == 'Personal Item'
    
    def test_convert_backlog_to_task(self):
        """Test converting backlog item to task via API"""
        backlog_item = BacklogItem.objects.create(
            title='Convert Me',
            source=BacklogItem.Source.CLIENT,
            created_by=self.user
        )
        
        url = reverse('backlog-convert-to-task', kwargs={'pk': backlog_item.pk})
        data = {
            'description': 'Converted task description',
            'priority': 'high',
            'project': self.project.pk
        }
        
        response = self.client.post(url, data)
        
        assert response.status_code == status.HTTP_201_CREATED
        assert 'task' in response.data
        assert 'backlog_item' in response.data
        
        # Check task was created
        task = Task.objects.get(id=response.data['task']['id'])
        assert task.title == 'Convert Me'
        assert task.description == 'Converted task description'
        assert task.priority == 'high'
        assert task.project == self.project
        
        # Check backlog item is marked as converted
        backlog_item.refresh_from_db()
        assert backlog_item.is_converted
        assert backlog_item.converted_to_task == task
    
    def test_convert_already_converted_item(self):
        """Test converting already converted backlog item"""
        backlog_item = BacklogItem.objects.create(
            title='Already Converted',
            source=BacklogItem.Source.PERSONAL,
            created_by=self.user
        )
        backlog_item.convert_to_task()
        
        url = reverse('backlog-convert-to-task', kwargs={'pk': backlog_item.pk})
        response = self.client.post(url, {})
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'already been converted' in response.data['error']


@pytest.mark.django_db(transaction=True)
class TestTaskChecklistAPI:
    """Test TaskChecklist API endpoints"""
    
    def setup_method(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='testpass123'
        )
        self.task = Task.objects.create(
            title='Test Task',
            created_by=self.user
        )
        self.other_task = Task.objects.create(
            title='Other Task',
            created_by=self.other_user
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
    
    def test_create_checklist_item(self):
        """Test creating checklist item via API"""
        url = reverse('task-checklist-list', kwargs={'task_pk': self.task.pk})
        data = {
            'title': 'New Checklist Item',
            'position': 1
        }
        
        response = self.client.post(url, data)
        
        assert response.status_code == status.HTTP_201_CREATED
        assert TaskChecklist.objects.count() == 1
        
        checklist_item = TaskChecklist.objects.first()
        assert checklist_item.title == 'New Checklist Item'
        assert checklist_item.task == self.task
        assert checklist_item.position == 1
    
    def test_list_task_checklists(self):
        """Test listing checklist items for a task"""
        TaskChecklist.objects.create(
            task=self.task,
            title='Item 1',
            position=1
        )
        TaskChecklist.objects.create(
            task=self.task,
            title='Item 2',
            position=2
        )
        TaskChecklist.objects.create(
            task=self.other_task,
            title='Other Item',
            position=1
        )
        
        url = reverse('task-checklist-list', kwargs={'task_pk': self.task.pk})
        response = self.client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 2
        assert response.data['results'][0]['title'] == 'Item 1'
        assert response.data['results'][1]['title'] == 'Item 2'
    
    def test_toggle_checklist_completion(self):
        """Test toggling checklist item completion"""
        checklist_item = TaskChecklist.objects.create(
            task=self.task,
            title='Toggle Me',
            position=1
        )
        
        url = reverse('task-checklist-toggle', kwargs={
            'task_pk': self.task.pk,
            'pk': checklist_item.pk
        })
        
        # Toggle to completed
        response = self.client.post(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'marked as completed' in response.data['message']
        
        checklist_item.refresh_from_db()
        assert checklist_item.is_completed
        
        # Toggle back to incomplete
        response = self.client.post(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'marked as incomplete' in response.data['message']
        
        checklist_item.refresh_from_db()
        assert not checklist_item.is_completed
    
    def test_access_other_user_task_checklist(self):
        """Test that users cannot access other users' task checklists"""
        url = reverse('task-checklist-list', kwargs={'task_pk': self.other_task.pk})
        
        response = self.client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 0  # No access to other user's tasks


@pytest.mark.django_db(transaction=True)
class TestTaskDetailWithChecklists:
    """Test TaskDetailSerializer with checklist integration"""
    
    def setup_method(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.task = Task.objects.create(
            title='Task with Checklists',
            created_by=self.user
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
    
    def test_task_detail_includes_checklists(self):
        """Test that task detail includes checklist items"""
        # Create some checklist items
        TaskChecklist.objects.create(
            task=self.task,
            title='Item 1',
            position=1,
            is_completed=True
        )
        TaskChecklist.objects.create(
            task=self.task,
            title='Item 2',
            position=2,
            is_completed=False
        )
        TaskChecklist.objects.create(
            task=self.task,
            title='Item 3',
            position=3,
            is_completed=True
        )
        
        url = reverse('task-detail', kwargs={'pk': self.task.pk})
        response = self.client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        
        # Check checklist data is included
        assert 'checklist_items' in response.data
        assert len(response.data['checklist_items']) == 3
        
        # Check progress calculations
        assert response.data['checklist_total_count'] == 3
        assert response.data['checklist_completed_count'] == 2
        assert response.data['checklist_progress_percentage'] == 66.7
    
    def test_task_detail_no_checklists(self):
        """Test task detail with no checklist items"""
        url = reverse('task-detail', kwargs={'pk': self.task.pk})
        response = self.client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['checklist_items'] == []
        assert response.data['checklist_total_count'] == 0
        assert response.data['checklist_completed_count'] == 0
        assert response.data['checklist_progress_percentage'] == 0
