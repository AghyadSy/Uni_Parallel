from pathlib import Path
import os
from urllib.parse import parse_qs, unquote, urlparse


BASE_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "unsafe-demo-secret-key")
DEBUG = os.environ.get("DJANGO_DEBUG", "True").lower() == "true"
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "apps.products",
    "apps.orders",
    "apps.payments",
    "apps.jobs",
    "apps.reports",
    "apps.monitoring",
    "apps.demo",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "core.aop.performance.PerformanceMonitoringMiddleware",
    "core.aop.demo_mode.DemoModeMiddleware",
    "core.aop.error_handling.ErrorHandlingMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"


def _database_config():
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if database_url:
        parsed = urlparse(database_url)
        if parsed.scheme not in {"postgres", "postgresql"}:
            raise ValueError("DATABASE_URL must use postgres:// or postgresql://")

        options = {}
        ssl_mode = parse_qs(parsed.query).get("sslmode", [os.environ.get("POSTGRES_SSLMODE", "").strip()])[0]
        if ssl_mode:
            options["sslmode"] = ssl_mode

        return {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": unquote(parsed.path.lstrip("/")) or os.environ.get("POSTGRES_DB", "backend"),
            "USER": unquote(parsed.username or os.environ.get("POSTGRES_USER", "postgres")),
            "PASSWORD": unquote(parsed.password or os.environ.get("POSTGRES_PASSWORD", "postgres")),
            "HOST": parsed.hostname or os.environ.get("POSTGRES_HOST", "127.0.0.1"),
            "PORT": str(parsed.port or os.environ.get("POSTGRES_PORT", "5432")),
            "CONN_MAX_AGE": int(os.environ.get("POSTGRES_CONN_MAX_AGE", "60")),
            "CONN_HEALTH_CHECKS": True,
            "OPTIONS": options,
        }

    options = {}
    ssl_mode = os.environ.get("POSTGRES_SSLMODE", "").strip()
    if ssl_mode:
        options["sslmode"] = ssl_mode

    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "backend"),
        "USER": os.environ.get("POSTGRES_USER", "postgres"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "aghyad"),
        "HOST": os.environ.get("POSTGRES_HOST", "127.0.0.1"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        "CONN_MAX_AGE": int(os.environ.get("POSTGRES_CONN_MAX_AGE", "60")),
        "CONN_HEALTH_CHECKS": True,
        "OPTIONS": options,
    }


DATABASES = {
    "default": _database_config(),
}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REDIS_URL = os.environ.get("REDIS_URL", "").strip()

if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": REDIS_URL,
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
            },
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "high-performance-ecommerce",
        }
    }

REST_FRAMEWORK = {
    "EXCEPTION_HANDLER": "core.exceptions.custom_exception_handler",
}

ALLOW_UNSAFE_DEMO_MODE = os.environ.get("ALLOW_UNSAFE_DEMO_MODE", "True").lower() == "true"
DEMO_INVOICE_DELAY_SECONDS = float(os.environ.get("DEMO_INVOICE_DELAY_SECONDS", "0.8"))
DEMO_BACKGROUND_JOB_DELAY_SECONDS = float(os.environ.get("DEMO_BACKGROUND_JOB_DELAY_SECONDS", "0.1"))
DEMO_RACE_INITIAL_STOCK = int(os.environ.get("DEMO_RACE_INITIAL_STOCK", "500"))

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "readable": {
            "format": "%(asctime)s %(levelname)s [%(name)s] %(message)s",
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "readable",
        },
        "file": {
            "class": "logging.FileHandler",
            "filename": LOG_DIR / "app.log",
            "formatter": "readable",
            "encoding": "utf-8",
        },
    },
    "root": {
        "handlers": ["console", "file"],
        "level": "INFO",
    },
    "loggers": {
        "django.db.backends": {
            "level": "WARNING",
        }
    },
}
