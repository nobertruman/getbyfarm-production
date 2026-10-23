"""
GetbyFarm Django settings — production-oriented.

Every secret and environment-specific value comes from environment variables.
The app refuses to start in production (DJANGO_DEBUG != true) without a real
SECRET_KEY and explicit ALLOWED_HOSTS — it fails closed instead of silently
running with insecure defaults.
"""
import os
from datetime import timedelta
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


DEBUG = env_bool("DJANGO_DEBUG", False)

# ---------------------------------------------------------------- core / secrets
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "dev-only-insecure-key-never-use-in-production"
    else:
        raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set when DJANGO_DEBUG is not true.")
elif not DEBUG and (len(SECRET_KEY) < 50 or SECRET_KEY.startswith("change-me")):
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY looks weak or is still the placeholder. Generate one with: "
        "python -c \"from django.core.management.utils import get_random_secret_key as g; print(g())\""
    )

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1" if DEBUG else "")
# Render sets RENDER_EXTERNAL_HOSTNAME (e.g. myapp.onrender.com) and its health checks use that Host header.
_RENDER_HOST = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "").strip()
if _RENDER_HOST and _RENDER_HOST not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(_RENDER_HOST)
if not DEBUG and not ALLOWED_HOSTS:
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS must be set (comma-separated) in production.")

# ---------------------------------------------------------------- apps / middleware
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.admin",
    "django.contrib.messages",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "django_filters",
    # GetbyFarm apps
    "accounts",
    "organizations",
    "suppliers",
    "catalog",
    "pricing",
    "procurement",
    "carts",
    "orders",
    "payments",
    "invoices",
    "deliveries",
    "analytics",
    "notifications",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
AUTH_USER_MODEL = "accounts.User"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# ---------------------------------------------------------------- database
# DATABASE_URL (Render/Railway/Fly/Heroku style) wins; otherwise discrete DB_* vars.
if os.environ.get("DATABASE_URL"):
    DATABASES = {
        "default": dj_database_url.config(
            conn_max_age=60,
            conn_health_checks=True,
            ssl_require=env_bool("DB_SSL_REQUIRE", False),
        )
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("DB_NAME", "getbyfarm"),
            "USER": os.environ.get("DB_USER", "getbyfarm"),
            "PASSWORD": os.environ.get("DB_PASSWORD", ""),
            "HOST": os.environ.get("DB_HOST", "localhost"),
            "PORT": os.environ.get("DB_PORT", "5432"),
            "CONN_MAX_AGE": 60,
            "CONN_HEALTH_CHECKS": True,
        }
    }

# ---------------------------------------------------------------- cache (rate limiting needs a SHARED cache)
# Django's default cache is per-process memory: with several gunicorn workers every worker would keep its own
# rate-limit counters, silently multiplying every limit. So we use a cache all workers share:
#   - REDIS_URL set  -> Redis (recommended once you run more than one server)
#   - otherwise      -> a table in the same Postgres database (zero extra infrastructure; `createcachetable`
#                       runs in docker-entrypoint.sh).
if os.environ.get("REDIS_URL"):
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": os.environ["REDIS_URL"]}}
else:
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.db.DatabaseCache", "LOCATION": "django_cache"}}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------- REST framework / JWT
_renderers = ["rest_framework.renderers.JSONRenderer"]
if DEBUG:
    _renderers.append("rest_framework.renderers.BrowsableAPIRenderer")

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ("rest_framework_simplejwt.authentication.JWTAuthentication",),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_FILTER_BACKENDS": ("django_filters.rest_framework.DjangoFilterBackend",),
    "DEFAULT_RENDERER_CLASSES": _renderers,
    "DEFAULT_PAGINATION_CLASS": "config.pagination.StandardPagination",
    "PAGE_SIZE": 50,
    "DEFAULT_THROTTLE_CLASSES": (
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
        "rest_framework.throttling.ScopedRateThrottle",
    ),
    # Strict defaults; override per environment (e.g. CI's end-to-end test registers and logs in far more often than a human).
    "DEFAULT_THROTTLE_RATES": {
        "anon": os.environ.get("THROTTLE_ANON", "60/minute"),
        "user": os.environ.get("THROTTLE_USER", "240/minute"),
        "login": os.environ.get("THROTTLE_LOGIN", "10/minute"),         # brute-force protection on login/refresh
        "register": os.environ.get("THROTTLE_REGISTER", "10/hour"),     # signup spam protection
        "payment": os.environ.get("THROTTLE_PAYMENT", "6/minute"),      # each STK push prompts a real phone
    },
    "EXCEPTION_HANDLER": "rest_framework.views.exception_handler",
    # Behind the reverse proxy every request arrives from the proxy's IP. NUM_PROXIES makes throttling key on
    # the real client address (from X-Forwarded-For) instead of lumping all users into one rate-limit bucket.
    "NUM_PROXIES": int(os.environ.get("NUM_PROXIES", "0" if DEBUG else "1")),
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,   # a stolen, already-used refresh token stops working
    "UPDATE_LAST_LOGIN": True,
}

# ---------------------------------------------------------------- CORS / CSRF
# Recommended deployment serves frontend and API from ONE origin (reverse proxy), which
# needs no CORS at all. These only matter if you host them on separate domains.
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", "http://localhost:3000" if DEBUG else "")
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", "")
if _RENDER_HOST and f"https://{_RENDER_HOST}" not in CSRF_TRUSTED_ORIGINS:
    CSRF_TRUSTED_ORIGINS.append(f"https://{_RENDER_HOST}")

# ---------------------------------------------------------------- HTTPS / security headers
if not DEBUG:
    # TLS terminates at the reverse proxy (Caddy); it forwards X-Forwarded-Proto.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", False)  # proxy already redirects HTTP->HTTPS
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", 31536000))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", False)
    SECURE_HSTS_PRELOAD = False
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

# ---------------------------------------------------------------- static files (admin) via WhiteNoise
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# ---------------------------------------------------------------- payments (M-Pesa Daraja)
MPESA_CONFIG = {
    "ENABLED": env_bool("MPESA_ENABLED", False),
    "ENV": os.environ.get("MPESA_ENV", "sandbox"),  # sandbox | production
    "CONSUMER_KEY": os.environ.get("MPESA_CONSUMER_KEY", ""),
    "CONSUMER_SECRET": os.environ.get("MPESA_CONSUMER_SECRET", ""),
    "SHORTCODE": os.environ.get("MPESA_SHORTCODE", ""),
    "PASSKEY": os.environ.get("MPESA_PASSKEY", ""),
    # Public HTTPS base URL Safaricom will call back, e.g. https://app.example.com
    "CALLBACK_BASE_URL": os.environ.get("MPESA_CALLBACK_BASE_URL", ""),
    # Random secret embedded in the callback URL path. Daraja does not sign callbacks, so an
    # unguessable URL + matching against a payment we created is the primary defence.
    "CALLBACK_SECRET": os.environ.get("MPESA_CALLBACK_SECRET", ""),
    # CustomerPayBillOnline (Paybill) or CustomerBuyGoodsOnline (Till). For a Till, PartyB is the till number.
    "TRANSACTION_TYPE": os.environ.get("MPESA_TRANSACTION_TYPE", "CustomerPayBillOnline"),
    "TILL_OR_SHORTCODE": os.environ.get("MPESA_PARTY_B", ""),
}
# Explicit opt-in for the fake payment adapter (staging/demo only). Off by default so a
# production deploy can never "take payment" without actually taking payment.
ALLOW_MOCK_PAYMENTS = env_bool("ALLOW_MOCK_PAYMENTS", False)
if not DEBUG and ALLOW_MOCK_PAYMENTS and not env_bool("I_UNDERSTAND_MOCK_PAYMENTS_ARE_FAKE", False):
    raise ImproperlyConfigured(
        "ALLOW_MOCK_PAYMENTS=true marks orders as paid WITHOUT charging anyone. For a staging demo also set "
        "I_UNDERSTAND_MOCK_PAYMENTS_ARE_FAKE=true; never enable on a real production site."
    )

# ---------------------------------------------------------------- locale
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Nairobi"
USE_TZ = True
DEFAULT_COUNTRY_CODE = os.environ.get("DEFAULT_COUNTRY_CODE", "KE")

# ---------------------------------------------------------------- logging (stdout -> container logs)
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"std": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "std"}},
    "root": {"handlers": ["console"], "level": os.environ.get("LOG_LEVEL", "INFO")},
    "loggers": {"django.request": {"handlers": ["console"], "level": "WARNING", "propagate": False}},
}
