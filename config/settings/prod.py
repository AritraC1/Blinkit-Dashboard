"""Production settings.

All values are environment-driven: SECRET_KEY, ALLOWED_HOSTS, DATABASE_URL,
TIME_ZONE (base.py), DEBUG and SECURE_SSL_REDIRECT (here). Set a real
SECRET_KEY and ALLOWED_HOSTS in the environment before deploying.
"""
from .base import *  # noqa: F401,F403

DEBUG = env.bool("DEBUG", default=False)  # noqa: F405

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)  # noqa: F405
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
