import sys

sys.path.append("../example/")

DEBUG = True
USE_TZ = True

SECRET_KEY = "%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%"

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}

ROOT_URLCONF = "tests.urls"

INSTALLED_APPS = ["getpaid", "getpaid.backends.dummy", "orders"]

SITE_ID = 1

MIDDLEWARE = ()

GETPAID_ORDER_MODEL = "orders.Order"
GETPAID_PAYMENT_MODEL = "orders.CustomPayment"
