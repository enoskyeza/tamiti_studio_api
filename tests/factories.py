# tests/factories.py
import factory
from users.models import User
from factory.django import DjangoModelFactory
from projects.models import Project, Milestone, ProjectComment
from tasks.models import Task, TaskGroup
from common.enums import ProjectStatus,  PriorityLevel

class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda obj: f"{obj.username}@example.com")
    password = factory.PostGenerationMethodCall('set_password', 'testpass123')
    is_verified = True


class ProjectFactory(DjangoModelFactory):
    class Meta:
        model = Project

    name = factory.Sequence(lambda n: f"Project {n}")
    description = "Test project"
    client_name = "Client Inc."
    status = ProjectStatus.PLANNING
    priority = PriorityLevel.MEDIUM
    start_date = factory.Faker("date_this_year")
    due_date = factory.Faker("date_this_year")
    created_by = factory.SubFactory(UserFactory)


class MilestoneFactory(DjangoModelFactory):
    class Meta:
        model = Milestone

    project = factory.SubFactory(ProjectFactory)
    name = factory.Sequence(lambda n: f"Milestone {n}")
    due_date = factory.Faker("date_this_year")


class TaskFactory(DjangoModelFactory):
    class Meta:
        model = Task

    project = factory.SubFactory(ProjectFactory)
    title = factory.Sequence(lambda n: f"Task {n}")
    description = "A test task"
    priority = PriorityLevel.MEDIUM
    due_date = factory.Faker("future_datetime")
    created_by = factory.SubFactory(UserFactory)


class TaskGroupFactory(DjangoModelFactory):
    class Meta:
        model = TaskGroup

    project = factory.SubFactory(ProjectFactory)
    name = factory.Sequence(lambda n: f"Group {n}")


class ProjectCommentFactory(DjangoModelFactory):
    class Meta:
        model = ProjectComment

    project = factory.SubFactory(ProjectFactory)
    user = factory.SubFactory(UserFactory)
    content = "This is a comment"

