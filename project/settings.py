from pathlib import Path
import os

import environ


BASE_DIR = Path(__file__).resolve().parent.parent

# Load local values without overriding variables supplied by the shell or host.
environ.Env.read_env(BASE_DIR / ".env", overwrite=False)

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "replace-me-with-secure-key")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
MYMEMORY_BASE_URL = os.environ.get(
    "MYMEMORY_BASE_URL", "https://api.mymemory.translated.net"
)
MYMEMORY_CONTACT_EMAIL = os.environ.get("MYMEMORY_CONTACT_EMAIL", "")
MYMEMORY_API_KEY = os.environ.get("MYMEMORY_API_KEY", "")
MYMEMORY_TIMEOUT_SECONDS = float(
    os.environ.get("MYMEMORY_TIMEOUT_SECONDS", "10")
)
debug_value = os.environ.get("DJANGO_DEBUG", os.environ.get("DEBUG", "True"))
DEBUG = debug_value.lower() in {"1", "true", "yes", "on"}

allowed_hosts_value = os.environ.get(
    "DJANGO_ALLOWED_HOSTS",
    os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1"),
)
ALLOWED_HOSTS = [host.strip() for host in allowed_hosts_value.split(",") if host.strip()]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core",
    "accounts"
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "project.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
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

WSGI_APPLICATION = "project.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True

STATIC_URL = "/static/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "login"
