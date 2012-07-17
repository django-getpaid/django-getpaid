from settings import *


GETPAID_BACKENDS_SETTINGS = {
    # Please provide your settings for backends
    'getpaid.backends.payu' : {
        'pos_id' : 123456789,
        'key1' : 'xxx',
        'key2' : 'xxx',
        'pos_auth_key': 'xxx',
        'signing' : True,
        #        'testing' : True,
    },
    }

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse'
        }
    },
    'handlers': {
        'mail_admins': {
            'level': 'ERROR',
            'filters': ['require_debug_false'],
            'class': 'django.utils.log.AdminEmailHandler'
        },
        'console' : {
            'level':'DEBUG',
            'class':'logging.StreamHandler',

            },
        },
    'loggers': {
        'django.request': {
            'handlers': ['mail_admins'],
            'level': 'ERROR',
            'propagate': True,
            },


        #You can do some fancy logging ;)
        'getpaid.backends.payu':{
            'handlers': [],
            'level': 'DEBUG',
            }
    }
}
