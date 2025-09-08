from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'permissions', views.PermissionViewSet)
router.register(r'permission-groups', views.PermissionGroupViewSet)
router.register(r'permission-logs', views.PermissionLogViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('check-permission/', views.check_permission, name='check-permission'),
    path('user-permissions/', views.user_permissions, name='user-permissions'),
    path('content-type-permissions/', views.content_type_permissions, name='content-type-permissions'),
    path('clear-cache/', views.clear_permission_cache, name='clear-permission-cache'),
    path('stats/', views.permission_stats, name='permission-stats'),
]
