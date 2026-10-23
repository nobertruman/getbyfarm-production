"""Test settings: SQLite in memory so tests need no Postgres. Never use in production."""
import os

os.environ.setdefault("DJANGO_DEBUG", "true")
os.environ.setdefault("DJANGO_SECRET_KEY", "test-only-secret-key-that-is-long-enough-to-satisfy-jwt-hmac-minimums")

from config.settings import *  # noqa: F401,F403,E402

# CI/Postgres run: set TEST_DATABASE_URL=postgresql://user:pass@host/db (Django creates a test_ copy).
if os.environ.get("TEST_DATABASE_URL"):
    import dj_database_url
    DATABASES = {"default": dj_database_url.parse(os.environ["TEST_DATABASE_URL"])}
else:
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]  # fast tests only
STORAGES = {  # no manifest needed in tests
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
REST_FRAMEWORK = {**REST_FRAMEWORK, "DEFAULT_THROTTLE_RATES": {  # noqa: F405
    "anon": "10000/minute", "user": "10000/minute", "login": "10000/minute", "register": "10000/minute", "payment": "10000/minute",
}}

CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}  # fast, single-process tests
