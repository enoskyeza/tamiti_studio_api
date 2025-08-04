"""Utility functions for dispatching notifications.

This module centralizes notification creation so callers only need to
invoke :func:`dispatch_notification` instead of dealing with multiple
backends.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def dispatch_notification(user: Any, message: str, **context: Any) -> None:
    """Send a notification to ``user``.

    Parameters
    ----------
    user:
        The recipient of the notification. Typically a ``User`` instance or
        identifier.
    message:
        Human readable message content.
    **context:
        Extra metadata for future backends (e.g., URLs, identifiers).

    Notes
    -----
    - TODO: Emit notification events over Django Channels for real-time
      delivery to web clients.
    - TODO: Integrate external push notification and email providers.

    Currently this function only logs the notification which allows other
    parts of the codebase to start using a unified API.
    """

    logger.info("Dispatching notification to %s: %s", user, message)
