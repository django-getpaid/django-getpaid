from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = 'tests-default-payment-secret-key'
DEBUG = True
USE_I18N = False
USE_TZ = True
TIME_ZONE = 'UTC'
DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'

GETPAID_ORDER_MODEL = 'default_order_app.Order'
GETPAID_PAYMENT_MODEL = 'getpaid.Payment'

INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'getpaid',
    'tests.default_order_app',
]

MIDDLEWARE = []
ROOT_URLCONF = 'tests.urls_default_payment'
TEMPLATES = []

DATABASES = {
    'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}
}
