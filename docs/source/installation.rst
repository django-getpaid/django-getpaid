Installation
============

Gettings source code
--------------------

The source code of the first stable version will be available on pypi.

For now you can download development version from: https://github.com/cypreess/django-getpaid.git

Installing development version can be done using pip::

    $ pip install -e git+https://github.com/cypreess/django-getpaid.git#egg=django-getpaid


Enabling django application
---------------------------

Second step is to enable this django application by adding it to ``INSTALLED_APPS`` in your ``settings.py``::

        INSTALLED_APPS += ('getpaid', )

and add getpaid to your project's urls.py::

    url(r'^getpaid/', include('getpaid.urls', namespace='getpaid', app_name='getpaid')),

.. warning:: It is advised that
 you pass ``namespace`` and ``app_name`` as kwargs to include.


Enabling getpaid backends
-------------------------

Create any iterable (tuple or list) named ``GETPAID_BACKENDS`` and provide full path for backends that you want to enable in your project. E.g.::

    GETPAID_BACKENDS = ('getpaid.backends.dummy',
                        'getpaid.backends.payu', )



After that put also in your ``settings.py`` a dictionary ``GETPAID_BACKENDS_SETTINGS``. This will keep all configurations specific to a single backend. Keys of this dictionary should be a full path of getpaid backends. Please refer to :doc:`backends` section for names of available backends.

Each key should provide another dictonary object with some set of ``key->value`` pairs that are actual configuration settings for given backend::

    GETPAID_BACKENDS_SETTINGS = {
        # Please provide your settings for backends
        'getpaid.backends.payu' : {

            },
    }


Tests
-----

Some tests are provided in getpaid_test_project/tests.py as a django test suite. You can run them with::

    $ ./manage.py test orders --settings=getpaid_test_project.settings_test

