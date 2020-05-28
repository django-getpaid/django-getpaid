# Minimalistic settings
import os

from django.urls import reverse_lazy

os.environ["PYTHONBREAKPOINT"] = "ipdb.set_trace"

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SECRET_KEY = "=================================================="

DEBUG = True

GETPAID_ORDER_MODEL = "orders.Order"
GETPAID_PAYMENT_MODEL = "orders.CustomPayment"
GETPAID_DUMMY_SLUG = "getpaid.backends.dummy"
GETPAID_PAYU_SLUG = "getpaid.backends.payu"
GETPAID_BACKEND_HOST = "http://localhost:8080/"
GETPAID_FRONTEND_HOST = "http://localhost/"

GETPAID_BACKEND_SETTINGS = {
    GETPAID_DUMMY_SLUG: {
        "pos_id": 12345,
        "second_key": "91ae651578c5b5aa93f2d38a9be8ce11",
        "client_id": 12345,
        "client_secret": "12f071174cb7eb79d4aac5bc2f07563f",
        "confirmation_method": "push",
        "gateway": reverse_lazy("paywall:gateway"),
    },
    GETPAID_PAYU_SLUG: {
        "pos_id": 300746,
        "second_key": "b6ca15b0d1020e8094d9b5f8d163db54",
        "oauth_id": 300746,
        "oauth_secret": "2ee86a66e5d97e3fadc400c9f19b065d",
        "confirmation_method": "PULL",
        "continue_url": "{frontend_url}platnosci/{payment_id}/koniec/",
        "is_marketplace": False,  # change products to shoppingCarts in paywall
    },
}

PAYWALL_MODE = "PAY"  # PAY for instant paying, LOCK for pre-auth

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.admin",
    "django.contrib.messages",
    "django.contrib.sessions",
    "django.contrib.contenttypes",
    "django_fsm",
    "getpaid",
    "getpaid.backends.dummy",
    "getpaid.backends.payu",
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

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.path.join(BASE_DIR, "db.sqlite3"),
    }
}

TIME_ZONE = "UTC"
USE_I18N = False
USE_TZ = True
