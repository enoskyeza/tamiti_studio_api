"""URL configuration for tamiti_studio project."""

from django.conf import settings
from django.contrib import admin
from django.urls import include, path

from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)


# Group all API endpoints under a versioned namespace
api_v1_patterns = [
    path('auth/', include('users.urls')),
    path('chat/', include('chatrooms.urls')),
    path('tasks/', include('tasks.urls')),
    path('users/', include('users.urls')),
    path('field/', include('field.urls')),
    path('projects/', include('projects.urls')),
    path('finance/', include('finance.urls')),
    path('assistants/', include('assistants.urls')),
    path('accounts/', include('accounts.urls')),
    path('social/', include('social.urls')),
    path('content/', include('content.urls')),
]


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/', include((api_v1_patterns, 'v1'), namespace='v1')),

    # Swagger / OpenAPI endpoints
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]


if settings.DEBUG:
    import debug_toolbar

    urlpatterns += [
        path('__debug__/', include(debug_toolbar.urls)),
    ]

