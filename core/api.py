import logging

from django.conf import settings
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.viewsets import ModelViewSet

logger = logging.getLogger(__name__)


class AppContextLoggingPermission(BasePermission):
    def has_permission(self, request, view):
        view_context = getattr(view, "context", None)
        token = getattr(request, "auth", None)
        token_app = None

        if token is not None:
            try:
                token_app = token.get("app")
            except AttributeError:
                if isinstance(token, dict):
                    token_app = token.get("app")

        # Always log mismatches for observability
        if view_context and token_app and view_context != token_app:
            logger.info(
                "App context mismatch",
                extra={
                    "view_context": view_context,
                    "token_app": token_app,
                    "user_id": getattr(request.user, "id", None),
                },
            )

        enforce = getattr(settings, "APP_CONTEXT_ENFORCEMENT", False)

        # When enforcement is disabled, behave as a pure logging permission
        if not enforce:
            return True

        # No context declared on the view -> treat as global/platform endpoint
        if not view_context:
            return True

        # No app claim on token -> allow for now but log for migration
        if token_app is None:
            logger.info(
                "App context missing on token",
                extra={
                    "view_context": view_context,
                    "user_id": getattr(request.user, "id", None),
                },
            )
            return True

        # Enforce strict match between token app and view context
        if view_context != token_app:
            return False

        return True


class ContextAwareModelViewSet(ModelViewSet):
    context = None
    permission_classes = [IsAuthenticated, AppContextLoggingPermission]
