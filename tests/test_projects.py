import pytest
from factories import (
    UserFactory, ProjectFactory, TaskFactory,
    TaskGroupFactory, MilestoneFactory, ProjectCommentFactory
)

@pytest.mark.django_db
def test_create_project():
    user = UserFactory()
    project = ProjectFactory(created_by=user)
    assert project.name.startswith("Project")
    assert project.created_by == user

@pytest.mark.django_db
def test_project_completion_percentage():
    project = ProjectFactory()
    TaskFactory.create_batch(3, project=project, is_completed=False)
    TaskFactory.create_batch(2, project=project, is_completed=True)
    project.update_completion_percentage()
    assert project.completion_percentage == 40

@pytest.mark.django_db
def test_create_milestone():
    milestone = MilestoneFactory()
    assert milestone.project is not None

@pytest.mark.django_db
def test_create_task_and_toggle():
    task = TaskFactory()
    assert not task.is_completed
    task.is_completed = True
    task.save()
    assert task.completed_at is not None

@pytest.mark.django_db
def test_create_task_group():
    group = TaskGroupFactory()
    assert group.name.startswith("Group")

@pytest.mark.django_db
def test_project_comment():
    project = ProjectFactory()
    comment = ProjectCommentFactory(project=project)
    assert comment.author is not None
    assert comment.content_type.model == 'project'
    assert comment.object_id == project.id
    assert "Comment" in str(comment)
