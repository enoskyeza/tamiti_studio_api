import pytest
from rest_framework.test import APIClient

from tests.factories import UserFactory, ProjectFactory, TaskFactory
from tasks.models import Task


@pytest.mark.django_db
def test_task_list_and_create():
    user = UserFactory()
    project = ProjectFactory(created_by=user)
    TaskFactory(project=project, created_by=user, title="Task A")
    TaskFactory(project=project, created_by=user, title="Task B")
    other_project = ProjectFactory()
    TaskFactory(project=other_project, title="Other Task")

    client = APIClient()
    client.force_authenticate(user=user)

    response = client.get("/api/tasks/")
    assert response.status_code == 200
    data = response.json()
    results = data.get("results", data) if isinstance(data, dict) else data
    titles = [t["title"] for t in results]
    assert "Task A" in titles and "Task B" in titles
    assert "Other Task" not in titles

    payload = {"project": project.id, "title": "Created Task"}
    response = client.post("/api/tasks/", payload)
    assert response.status_code == 201
    assert response.json()["title"] == "Created Task"
    assert Task.objects.filter(title="Created Task", project=project).exists()


@pytest.mark.django_db
def test_task_retrieve_update_delete():
    user = UserFactory()
    project = ProjectFactory(created_by=user)
    task = TaskFactory(project=project, created_by=user, title="Initial Title")

    client = APIClient()
    client.force_authenticate(user=user)

    url = f"/api/tasks/{task.id}/"
    response = client.get(url)
    assert response.status_code == 200
    assert response.json()["title"] == "Initial Title"

    response = client.patch(url, {"title": "Updated Title"})
    assert response.status_code == 200
    task.refresh_from_db()
    assert task.title == "Updated Title"

    response = client.delete(url)
    assert response.status_code == 204
    assert not Task.objects.filter(id=task.id).exists()


@pytest.mark.django_db
def test_toggle_task_completion():
    user = UserFactory()
    project = ProjectFactory(created_by=user)
    task = TaskFactory(project=project, created_by=user, is_completed=False)

    client = APIClient()
    client.force_authenticate(user=user)

    url = f"/api/tasks/{task.id}/toggle/"
    response = client.post(url)
    assert response.status_code == 200
    task.refresh_from_db()
    assert task.is_completed is True
