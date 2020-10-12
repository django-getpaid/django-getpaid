.. image:: https://img.shields.io/pypi/v/django-getpaid.svg
    :target: https://pypi.org/project/django-getpaid/
    :alt: Latest PyPI version
.. image:: https://img.shields.io/travis/sunscrapers/django-getpaid.svg
    :target: https://travis-ci.org/sunscrapers/django-getpaid
.. image:: https://api.codacy.com/project/badge/Coverage/d25ba81e2e4740d6aac356f4ac90b16d
    :target: https://www.codacy.com/manual/dekoza/django-getpaid
.. image:: https://img.shields.io/pypi/wheel/django-getpaid.svg
    :target: https://pypi.org/project/django-getpaid/
.. image:: https://img.shields.io/pypi/l/django-getpaid.svg
    :target: https://pypi.org/project/django-getpaid/
.. image:: https://api.codacy.com/project/badge/Grade/d25ba81e2e4740d6aac356f4ac90b16d
    :target: https://www.codacy.com/manual/dekoza/django-getpaid

=============================
Welcome to django-getpaid
=============================


django-getpaid is payment processing framework for Django

Documentation
=============

The full documentation is at https://django-getpaid.readthedocs.io.

Features
========

* support for multiple payment brokers at the same time
* very flexible architecture
* support for asynchronous status updates - both push and pull
* support for modern REST-based broker APIs
* support for multiple currencies (but one per payment)
* support for global and per-plugin validators
* easy customization with provided base abstract models and swappable mechanic (same as with Django's User model)


Quickstart
==========

Install django-getpaid and at least one payment backend:

.. code-block:: console

    pip install django-getpaid

Add them to your ``INSTALLED_APPS``:

.. code-block:: python

    INSTALLED_APPS = [
        ...
        'getpaid',
        'getpaid.backends.payu',  # one of plugins
        ...
    ]

Add getpaid to URL patterns:

.. code-block:: python

    urlpatterns = [
        ...
        path('payments/', include('getpaid.urls')),
        ...
    ]

Define an ``Order`` model by subclassing ``getpaid.models.AbstractOrder``
and define some required methods:

.. code-block:: python

    from getpaid.models import AbstractOrder

    class MyCustomOrder(AbstractOrder):
        amount = models.DecimalField(decimal_places=2, max_digits=8)
        description = models.CharField(max_length=128)
        buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

        def get_absolute_url(self):
            return reverse('order-detail', kwargs={"pk": self.pk})

        def get_total_amount(self):
            return self.amount

        def get_buyer_info(self):
            return {"email": self.buyer.email}

        def get_currency(self):
            return "EUR"

        def get_description(self):
            return self.description

.. note:: If you already have an Order model and don't want to subclass ``AbstractOrder``
    just make sure you implement all methods.

Inform getpaid of your Order model in ``settings.py`` and provide settings for payment backends:

.. code-block:: python

    GETPAID_ORDER_MODEL = 'yourapp.MyCustomOrder'
    GETPAID_PAYU_SLUG = "getpaid.backends.payu"

    GETPAID_BACKEND_SETTINGS = {
        GETPAID_PAYU_SLUG: {
            # take these from your merchant panel:
            "pos_id": 12345,
            "second_key": "91ae651578c5b5aa93f2d38a9be8ce11",
            "oauth_id": 12345,
            "oauth_secret": "12f071174cb7eb79d4aac5bc2f07563f",
        },
    }

Write a view that will create the Payment.

An example view and its hookup to urls.py can look like this:

.. code-block:: python

    # main urls.py

    urlpatterns = [
        # ...
        path("gp/", include("getpaid.urls")),
    ]

You can optionally override callback handler. Example for PayU backend:

.. code-block:: python

    from getpaid.backends.payu.processor import PaymentProcessor as GetpaidPayuProcessor

    class PayuCallbackHandler:
        def __init__(self, payment):
            self.payment = payment

        def handle(self, data):
            pass

    class PayuPaymentProcessor(GetpaidPayuProcessor):
        callback_handler_class = PayuCallbackHandler

=============================
PAYU
=============================
TODO: improve docs

Running Tests
=============

.. code-block:: console

    poetry install
    poetry run tox


Alternatives
============

* `django-payments <https://github.com/mirumee/django-payments>`_


Credits
=======

Created by `Krzysztof Dorosz <https://github.com/cypreess>`_.
Redesigned and rewritten by `Dominik Kozaczko <https://github.com/dekoza>`_.

Proudly sponsored by `SUNSCRAPERS <http://sunscrapers.com/>`_


Disclaimer
==========

This project has nothing in common with `getpaid <http://code.google.com/p/getpaid/>`_ plone project.
