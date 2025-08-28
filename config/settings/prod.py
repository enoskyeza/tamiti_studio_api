from .base import *
from decouple import Csv, config


DEBUG = False

ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="tamiti.pythonanywhere.com", cast=Csv())
CSRF_TRUSTED_ORIGINS = config(
    "CSRF_TRUSTED_ORIGINS",
    default=f"https://{ALLOWED_HOSTS[0]}",
    cast=Csv()
)

CORS_ALLOWED_ORIGINS = config("CORS_ALLOWED_ORIGINS", default="https://studio.tamiti.com", cast=Csv())
CORS_ALLOW_CREDENTIALS = False

MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")

INSTALLED_APPS += ["whitenoise.runserver_nostatic", "corsheaders"]

STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
}

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True


