from django.urls import path

from . import views


urlpatterns = [
    path("summary/projects/", views.ProjectSummaryView.as_view(), name="project-summary"),
    path("summary/tasks/", views.TaskSummaryView.as_view(), name="task-summary"),
    path("summary/finance/", views.FinanceSummaryView.as_view(), name="finance-summary"),
    path("summary/field/", views.FieldSummaryView.as_view(), name="field-summary"),
    path("summary/leads/", views.LeadsSummaryView.as_view(), name="leads-summary"),
    path("summary/socials/", views.SocialSummaryView.as_view(), name="social-summary"),
    path("kpis/", views.DashboardKPIView.as_view(), name="dashboard-kpis"),
]

