# Minimalistic settings
import os

os.environ["PYTHONBREAKPOINT"] = "ipdb.set_trace"

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SECRET_KEY = "=================================================="

DEBUG = True

GETPAID_ORDER_MODEL = "orders.Order"
GETPAID_PAYMENT_MODEL = "orders.CustomPayment"
GETPAID_PAYOUT_MODEL = "orders.CustomPayout"

CONFIRMATION_METHOD = "PUSH"
REGISTRATION_METHOD = "REST"

GETPAID_TRANSFER_SLUG = "getpaid.backends.transfer"
GETPAID_DUMMY_SLUG = "getpaid.backends.dummy"
GETPAID_PAYU_SLUG = "getpaid.backends.payu"
GETPAID_BACKEND_HOST = "http://localhost:8080/"
GETPAID_FRONTEND_HOST = "http://localhost/"

GETPAID_BACKEND_SETTINGS = {
    GETPAID_DUMMY_SLUG: {
        "confirmation_method": CONFIRMATION_METHOD,
        "paywall_method": REGISTRATION_METHOD,
        # "push" for automatic callback,
        # "pull" if you want to call fetch_status separately
    },
    GETPAID_TRANSFER_SLUG: {
        # "message_template_name": "payments/message_template_name.html,
    },
    GETPAID_PAYU_SLUG: {
        "pos_id": 300746,
        "second_key": "b6ca15b0d1020e8094d9b5f8d163db54",
        "oauth_id": 300746,
        "oauth_secret": "2ee86a66e5d97e3fadc400c9f19b065d",
        "confirmation_method": "PULL",  # required for local testing
        "continue_url": "{frontend_host}platnosci/{payment_id}/koniec/",
        "is_marketplace": False,  # change products to shoppingCarts in paywall
    },
}

PAYWALL_MODE = "LOCK"  # PAY for instant paying, LOCK for pre-auth

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.admin",
    "django.contrib.messages",
    "django.contrib.sessions",
    "django.contrib.contenttypes",
    "getpaid",
    "getpaid.backends.dummy",
    "getpaid.backends.payu",
    "getpaid.backends.transfer",
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
