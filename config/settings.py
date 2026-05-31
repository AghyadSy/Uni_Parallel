from pathlib import Path
import os


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

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
        "OPTIONS": {
            "timeout": 30,
        },
    }
}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

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
DEMO_RACE_INITIAL_STOCK = int(os.environ.get("DEMO_RACE_INITIAL_STOCK", "5"))

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
