from .base import *

DEBUG = True

INSTALLED_APPS += ['debug_toolbar']
MIDDLEWARE.insert(1, 'debug_toolbar.middleware.DebugToolbarMiddleware')

INTERNAL_IPS = ["127.0.0.1"]
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
CORS_ALLOW_ALL_ORIGINS = DEBUG
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://localhost:5173",  # Vite dev server
    "https://studio.tamiti.com",
]
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://localhost:5173",  # Vite dev server
    "https://studio.tamiti.com",
]

# Cookie security settings for development
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'

# Refresh token cookies should remain cross-site to support frontend on a different port
REFRESH_COOKIE_SECURE = False
REFRESH_COOKIE_SAMESITE = 'Lax'  # Changed from 'None' to 'Lax' for development

# Cookie domain settings for cross-port development
SESSION_COOKIE_DOMAIN = None  # Allow cookies to work across localhost ports

# CORS settings for development
CORS_ALLOW_CREDENTIALS = True
