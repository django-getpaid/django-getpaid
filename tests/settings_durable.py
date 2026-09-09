"""Downstream swap and independent database alias, never example.Order."""

from copy import deepcopy

from tests.settings_default_payment import *  # noqa: F403
from tests.settings_default_payment import DATABASES as BASE_DATABASES

GETPAID_ORDER_MODEL = 'durable_test_app.Order'
GETPAID_PAYMENT_MODEL = 'durable_test_app.Payment'
INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'getpaid',
    'tests.durable_test_app',
    # tests.conftest registers the legacy PaywallEntryFactory.
    'paywall',
]
DATABASES = deepcopy(BASE_DATABASES)
DATABASES['storage'] = deepcopy(DATABASES['default'])
if DATABASES['storage']['ENGINE'] == 'django.db.backends.postgresql':
    DATABASES['storage']['NAME'] += '_storage'
