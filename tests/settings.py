# -*- coding: utf-8
from __future__ import unicode_literals, absolute_import
import sys

sys.path.append('../example/')

DEBUG = True
USE_TZ = True

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = "%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

ROOT_URLCONF = "tests.urls"

INSTALLED_APPS = [
    "getpaid",
    "getpaid.backends.dummy",
    'orders',
]

SITE_ID = 1

MIDDLEWARE = ()

GETPAID_ORDER_MODEL = 'orders.Order'
