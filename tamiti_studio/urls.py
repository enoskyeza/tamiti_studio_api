"""
URL configuration for tamiti_studio project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings

from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('users.urls')),
    path('api/chat/', include('chatrooms.urls')),
    path('api/tasks/', include('tasks.urls')),
    path('api/users/', include('users.urls')),
    path('api/field/', include('field.urls')),
    path('api/projects/', include('projects.urls')),
    path('api/finance/', include('finance.urls')),
    path('api/assistants/', include('assistants.urls')),
    path('api/accounts/', include('accounts.urls')),
    path('api/social/', include('social.urls')),
    path('api/content/', include('content.urls')),
    path('api/notifications/', include('notifications.urls')),
    path('api/dashboard/', include('dashboard.urls')),
    path('api/notifications/', include('notifications.urls')),

    # swagger endpoints
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),

]

# debug too settings
if settings.DEBUG:
    import debug_toolbar
    urlpatterns += [
        path("__debug__/", include(debug_toolbar.urls)),
    ]
