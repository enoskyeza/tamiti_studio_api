from .base import *

DEBUG = True

INSTALLED_APPS += ['debug_toolbar']
MIDDLEWARE.insert(1, 'debug_toolbar.middleware.DebugToolbarMiddleware')

INTERNAL_IPS = ["127.0.0.1"]
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
CORS_ALLOW_ALL_ORIGINS = DEBUG
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "https://studio.tamiti.com",
]
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:3000",
    "https://studio.tamiti.com",
]