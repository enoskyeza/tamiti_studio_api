"""Common exception handlers for the project."""

from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status


def custom_exception_handler(exc, context):
    """Return a consistent error response structure."""
    response = exception_handler(exc, context)

    if response is None:
        # If DRF couldn't handle the exception, fall back to a generic 500.
        return Response(
            {"errors": [str(exc)]}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    return Response({"errors": response.data}, status=response.status_code)

