# Minimalistic settings
import os

from django.urls import reverse_lazy

os.environ['PYTHONBREAKPOINT'] = 'ipdb.set_trace'

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SECRET_KEY = '=================================================='

DEBUG = True

GETPAID_ORDER_MODEL = 'orders.Order'
GETPAID_PAYMENT_MODEL = 'orders.CustomPayment'

# Configure payment backends via environment variables
# For production: set env vars to override sandbox keys
# For development: sandbox keys are used by default

GETPAID_BACKEND_SETTINGS = {
    'getpaid.backends.dummy': {
        'pos_id': int(os.environ.get('DUMMY_POS_ID', '12345')),
        'second_key': os.environ.get(
            'DUMMY_SECOND_KEY', '91ae651578c5b5aa93f2d38a9be8ce11'
        ),
        'client_id': int(os.environ.get('DUMMY_CLIENT_ID', '12345')),
        'client_secret': os.environ.get(
            'DUMMY_CLIENT_SECRET', '12f071174cb7eb79d4aac5bc2f07563f'
        ),
        'confirmation_method': 'push',
        'gateway': reverse_lazy('paywall:gateway'),
    },
    'getpaid_payu.processor.PayUProcessor': {
        'pos_id': int(os.environ.get('PAYU_POS_ID', '300746')),
        'second_key': os.environ.get(
            'PAYU_SECOND_KEY', 'b6ca15b0d1020e8094d9b5f8d163db54'
        ),
        'oauth_id': int(os.environ.get('PAYU_OAUTH_ID', '300746')),
        'oauth_secret': os.environ.get(
            'PAYU_OAUTH_SECRET', '2ee86a66e5d97e3fadc400c9f19b065d'
        ),
        'sandbox': True,
    },
    'getpaid_paynow.processor.PaynowProcessor': {
        'api_key': os.environ.get(
            'PAYNOW_API_KEY', 'd2e1d881-40b0-4b7e-9168-181bae3dc4e0'
        ),
        'signature_key': os.environ.get(
            'PAYNOW_SIGN_KEY', '8e42a868-5562-440d-817c-4921632fb049'
        ),
        'sandbox': True,
    },
}

PAYWALL_MODE = 'PAY'  # PAY for instant paying, LOCK for pre-auth

INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.admin',
    'django.contrib.messages',
    'django.contrib.sessions',
    'django.contrib.contenttypes',
    'getpaid',
    'getpaid.backends.dummy',
    'orders',
    'paywall',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
]

ROOT_URLCONF = 'example.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
            ]
        },
    }
]

WSGI_APPLICATION = 'example.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    }
}

TIME_ZONE = 'UTC'
USE_I18N = False
USE_TZ = True
