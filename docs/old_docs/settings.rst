Settings
========

``GETPAID_BACKENDS``
--------------------

**Required**

Iterable with fully qualified python importable names of backends.

Example::

        GETPAID_BACKENDS = ('getpaid.backends.dummy',
                            'getpaid.backends.payu', )

.. note::

    The very common thing what are also should do, never to forget adding backends also to ``INSTALLED_APPS``,
    is to add following line::

        INSTALLED_APPS += GETPAID_BACKENDS



``GETPAID_BACKENDS_SETTINGS``
-----------------------------

**Optional**

Dict that keeps backend specific configurations. Keys of this dictionary should be a fully qualified path of getpaid backends.
Each key should be another dict with a backed specific keys.
Please referrer to :doc:`backends` section for names of available backends and theirs specific required keys.

Default: ``{}``

Example::

    GETPAID_BACKENDS_SETTINGS = {
        'getpaid.backends.transferuj' : {
                'id' : 123456,
                'key' : 'xxxxxxxxxxxxx',
                'signing' : True,       # optional
            },
    }


.. warning::

    In spite of the fact that this setting is optional (e.g. not needed if only the dummy backend is used)
    every real backend requires some additional configuration, and will raise ImproperlyConfigured if
    required values are not provided.


``GETPAID_ORDER_DESCRIPTION``
-----------------------------

**Optional**

String in Django template format used to render name of order submitted to payment broker. If the value is
omitted or it evals to False, unicode representation of Order object will be used.

The following context variables are available inside the template:

**order**
    order object

**payment**
    payment object

Example::

    GETPAID_ORDER_DESCRIPTION = "Order {{ order.id }} - {{ order.name }}"


.. note::

    Setting this value has sense only if you are going to make ``Order.__unicode__()`` very custom, not suitable for
    presenting to user. Usually you should just define ``__unicode__`` method on your ``Order`` object
    and use it everywhere in the system.


``GETPAID_ORDER_MODEL``
-----------------------

**Optional**
String describing model name.

Example::

    GETPAID_ORDER_MODEL = 'my_super_app.Order'


.. note::

    Required for django >=1.7


``GETPAID_SUCCESS_URL_NAME``
-----------------------

**Optional**
Success URL name where the payment backend should return to on success

Example::

    GETPAID_SUCCESS_URL_NAME = 'order_payment_success'
    
    
``GETPAID_FAILURE_URL_NAME``
-----------------------

**Optional**
Success URL name where the payment backend should return to on failure

Example::

    GETPAID_FAILURE_URL_NAME = 'order_payment_failure'
