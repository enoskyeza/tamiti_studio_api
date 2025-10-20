class SaccoTenantMiddleware:
    """
    Automatically inject SACCO context into requests
    Phase 1: Foundation
    """
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Set SACCO context if user is authenticated
        if request.user.is_authenticated:
            try:
                if hasattr(request.user, 'sacco_membership'):
                    request.sacco = request.user.sacco_membership.sacco
                else:
                    request.sacco = None
            except Exception:
                request.sacco = None
        else:
            request.sacco = None
        
        response = self.get_response(request)
        return response
