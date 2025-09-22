from .base import *
from decouple import Csv, config


DEBUG = False

ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="tamiti.pythonanywhere.com", cast=Csv())
CSRF_TRUSTED_ORIGINS = config(
    "CSRF_TRUSTED_ORIGINS",
    default=f"https://{ALLOWED_HOSTS[0]}",
    cast=Csv()
)

CORS_ALLOWED_ORIGINS = config(
    "CORS_ALLOWED_ORIGINS",
    default="https://studio.tamiti.com,https://events.tamiti.com",
    cast=Csv(),
)
CORS_ALLOW_CREDENTIALS = True

MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")

INSTALLED_APPS += ["whitenoise.runserver_nostatic"]

STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
}

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Cross-origin cookie settings for production (tamiti.com -> app.pythonanywhere.com)
SESSION_COOKIE_SAMESITE = 'None'  # Allow cross-origin cookies in production
CSRF_COOKIE_SAMESITE = 'None'

# Make cookies available to subdomains (so frontend middleware can read refresh_cookie)
# Set these via environment if domain differs
SESSION_COOKIE_DOMAIN = config("SESSION_COOKIE_DOMAIN", default=None)
CSRF_COOKIE_DOMAIN = config("CSRF_COOKIE_DOMAIN", default=None)

