#noinspection PyUnresolvedReferences
from settings import *

GETPAID_BACKENDS = (
    'getpaid.backends.dummy',
    'getpaid.backends.payu',
    'getpaid.backends.transferuj',
    'getpaid.backends.przelewy24',
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

}

