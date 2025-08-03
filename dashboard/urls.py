from django.urls import path
from . import views

urlpatterns = [
    path('summary/projects/', views.project_summary, name='project-summary'),
    path('summary/tasks/', views.task_summary, name='task-summary'),
    path('summary/finance/', views.finance_summary, name='finance-summary'),
    path('summary/field/', views.field_summary, name='field-summary'),
    path('summary/leads/', views.leads_summary, name='leads-summary'),
    path('summary/socials/', views.social_summary, name='social-summary'),
]
