from django.urls import path
from projects.views import (
    ProjectListCreateView, ProjectDetailView,
    MilestoneListCreateView, MilestoneDetailView,
    ProjectCommentListCreateView
)

urlpatterns = [
    path('', ProjectListCreateView.as_view(), name='project-list-create'),
    path('<int:pk>/', ProjectDetailView.as_view(), name='project-detail'),
    path('milestones/', MilestoneListCreateView.as_view(), name='milestone-list-create'),
    path('milestones/<int:pk>/', MilestoneDetailView.as_view(), name='milestone-detail'),
    path('<int:project_id>/comments/', ProjectCommentListCreateView.as_view(), name='project-comments'),
]
