Payment backends
================

Payment backends are plug-and-play django applications that will make all necessary work to handle payment process via different money brokers. In this way you can handle multiple payment providers (not only multiple payment methods!) what is wise considering e.g. breakdown or downtime of a single payment broker.

Each payment backend delivers a payment channel for a defined list of currencies. When using ``PaymentMethodForm`` for displaying available payment methods for order it will automatically filter payment methods regarding to provided payment currency. This is important as system is designed to handle payments in multiple currencies. If you need to support currency conversions you need to do it before calling payment method form in your part of application.

Just to have an overview a payment backend has a very flexible architecture, allowing it to introduce own logic, urls and even models.

Dummy backend
-------------
This is a mock of payment backend that can be used only for testing/demonstrating purposes.

Dummy backend is accepting only ``USD``, ``EUR`` or ``PLN`` currency transactions. After redirecting to payment page it will display a dummy form where you can accept or decline a payment.

Enable backend
``````````````
Add backend full path to ``GETPAID_BACKENDS`` setting::

    GETPAID_BACKENDS += ('getpaid.backends.dummy', )


Don't forget to add backend path also to ``INSTALLED_APPS``::

    INSTALLED_APPS += ('getpaid.backends.dummy', )

Setup backend
`````````````
No additional setup is needed for dummy backend.




PayU backend
------------
This backend can handle payment processing via Polish money broker `PayU <http://payu.pl>`_ which is currently a part of the biggest on Polish market e-commerce provider - Allegro Group.

PayU accepts only payments in ``PLN``.

Enable backend
``````````````
Add backend full path to ``GETPAID_BACKENDS`` setting::

    GETPAID_BACKENDS += ('getpaid.backends.payu', )


Don't forget to add backend path also to ``INSTALLED_APPS``::

    INSTALLED_APPS += ('getpaid.backends.payu', )


Setup backend
`````````````
In order to start working with PayU you will need to have an activated account in PayU service. In this service you will need to define a new Shop with new Point of Sale (POS). After that you will have an access to following configuration variables:
 * ``pos_id`` - identificator of POS,
 * ``key1`` - according to PayU documentation this is a string that is used to compute md5 signature send by Shop,
 * ``key2``- according to PayU documentation this is a string that is used to compute md5 signature send from Shop,
 * ``pos_auth_key`` - just a kind of secret password for POS.


You need to provide this information in ``GETPAID_BACKENDS_SETTINGS`` dictionary::

    GETPAID_BACKENDS_SETTINGS = {
        'getpaid.backends.payu' : {
                'pos_id' : 123456,
                'key1' : 'xxxxxxxxxxxxx',
                'key2' : 'xxxxxxxxxxxxx',
                'pos_auth_key': 'xxxxxxxxx',
                'signing' : True,       # optional
                'testing' : True,       # optional
            },
    }

There are some additional options you can provide:
 * ``signing`` - for security reasons PayU can check a signature of all data that is sent from your service while redirecting to payment gateway; unless you really know what you are doing, this should be always on; default is True;
 * ``testing`` - when you test your service you can enable this option, all payments for PayU will have predefined "Test Payment" method which is provided by PayU service (need to be enabled); default is False;


Additional information
``````````````````````

This backend is asynchronous (as PayU requires an asynchronous architecture - they send a "ping" message that a payment change a status, and you need to asynchronously request theirs service for details of what has changed). That means that this backend requires django-celery application. Please refer to django-celery documentation for any additional information.

If you just want to make a quick start with using django-getpaid and django-celery please remember that after successful installation and enabling django-celery in your project you will need to run celery workers in order to process asynchronous task that this application requires. You do that for example in this way::

    $ python manage.py celery worker --loglevel=info

