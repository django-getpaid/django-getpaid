# Minimalistic settings
import os

os.environ["PYTHONBREAKPOINT"] = "ipdb.set_trace"

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SECRET_KEY = "=================================================="

DEBUG = True

GETPAID_ORDER_MODEL = "orders.Order"
GETPAID_PAYMENT_MODEL = "orders.CustomPayment"
CONFIRMATION_METHOD = "PUSH"
REGISTRATION_METHOD = "REST"

GETPAID_BACKEND_SETTINGS = {
    "getpaid.backends.dummy": {
        "confirmation_method": CONFIRMATION_METHOD,
        "method": REGISTRATION_METHOD,
        # "push" for automatic callback,
        # "pull" if you want to call fetch_status separately
    },
}

PAYWALL_MODE = "LOCK"  # PAY for instant paying, LOCK for pre-auth

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.admin",
    "django.contrib.messages",
    "django.contrib.sessions",
    "django.contrib.contenttypes",
    "django_fsm",
    "getpaid",
    "getpaid.backends.dummy",
    "orders",
    "paywall",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

ROOT_URLCONF = "example.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, "templates")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
            ]
        },
    }
]

WSGI_APPLICATION = "example.wsgi.application"

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}

TIME_ZONE = "UTC"
USE_I18N = False
USE_TZ = True
