# noinspection PyUnresolvedReferences
import sys
from .settings import *

GETPAID_BACKENDS = (
    'getpaid.backends.dummy',
    'getpaid.backends.payu',
    'getpaid.backends.transferuj',
    'getpaid.backends.przelewy24',
    'getpaid.backends.epaydk',
)

GETPAID_BACKENDS_SETTINGS = {
    # Please provide your settings for backends
    'getpaid.backends.payu': {
        'pos_id': 123456789,
        'key1': 'xxx',
        'key2': 'xxx',
        'pos_auth_key': 'xxx',
        'signing': True,
        #        'testing' : True,
    },

    'getpaid.backends.transferuj': {
        'id': 1234,
        'key': 'AAAAAAAA',

    },

    'getpaid.backends.przelewy24': {
        'id': 1234,
        'crc': '1111111111111111',
    },

    'getpaid.backends.epaydk': {
        'merchantnumber': 'xxxxxxxx',
        'secret': '4e89ea552f492d6711a6c13f99a2a1d4',
    },

}

TEST_RUNNER = 'django_nose.NoseTestSuiteRunner'
NOSE_ARGS = [
    '--verbosity=2',
    '--with-yanc',
    '--cover-branches',
    '--with-coverage',
    '--cover-package=getpaid',
    '--cover-package=getpaid_test_project.orders',
    'getpaid',
    'getpaid_test_project.orders'
]

for arg in sys.argv:
    if arg.startswith('--tests='):
        NOSE_ARGS = [
            '--verbosity=2',
            '--stop',
            #            '--cover-erase',
            '--with-yanc',
        ]
        break
