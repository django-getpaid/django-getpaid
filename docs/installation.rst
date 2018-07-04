Installation
============

From PyPI
---------

    $ pip install django-getpaid


Development version
-------------------

    $ pip install -e git+https://github.com/cypreess/django-getpaid.git#egg=django-getpaid


Enabling django application
---------------------------

Second step is to enable this django application by adding it to ``INSTALLED_APPS`` in your ``settings.py``::

        INSTALLED_APPS = [
            ...
            'getpaid',
        ]

Then update your project's urls.py::

    url(r'^getpaid/', include('getpaid.urls', namespace='getpaid', app_name='getpaid')),

.. warning:: It is advised that
 you pass ``namespace`` and ``app_name`` as kwargs to include.


Enabling getpaid backends
-------------------------

Create any iterable (tuple or list) named ``GETPAID_BACKENDS`` and provide full path for backends that you want to enable in your project. E.g.::

    GETPAID_BACKENDS = (
        'getpaid.backends.dummy',
        'getpaid.backends.payu',
    )

Then add ``GETPAID_BACKENDS_SETTINGS`` dictionary that will keep all configurations for each backend. Keys in this dictionary should be full paths of getpaid backends. Please refer to :doc:`backends` section for names of available backends.

Each key should provide another dictonary object with some set of ``key->value`` pairs that are actual configuration settings for given backend::

    GETPAID_BACKENDS_SETTINGS = {
        'getpaid.backends.payu' : {
            'pos_id': 123456789,
            'key1': 'xxx',
            'key2': 'xxx',
            'pos_auth_key': 'xxx',
            'signing': True,
         },
    }


Tests
-----

Provided tests use example app. You can run whole suite of tests by launching

    $ tox
