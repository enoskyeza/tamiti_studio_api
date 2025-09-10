# common/middleware.py
from zoneinfo import ZoneInfo
from django.utils import timezone


class UserTimezoneMiddleware:
    """
    Middleware to activate user's timezone for each request.
    This ensures that datetime operations use the user's preferred timezone.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Get user timezone from preferences
        user_timezone = None
        if hasattr(request, 'user') and request.user.is_authenticated:
            try:
                user_timezone = getattr(
                    getattr(request.user, 'preferences', None), 
                    'timezone', 
                    None
                )
            except AttributeError:
                pass
        
        # Activate timezone if found, otherwise deactivate to use default
        if user_timezone:
            try:
                timezone.activate(ZoneInfo(user_timezone))
            except Exception:
                # If invalid timezone, fall back to default
                timezone.deactivate()
        else:
            timezone.deactivate()
        
        response = self.get_response(request)
        
        # Clean up - deactivate timezone after request
        timezone.deactivate()
        
        return response
