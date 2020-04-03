=============================
Welcome to django-getpaid
=============================

.. image:: https://img.shields.io/pypi/v/django-getpaid.svg
    :target: https://pypi.org/project/django-getpaid/
    :alt: Latest PyPI version
.. image:: https://img.shields.io/travis/sunscrapers/django-getpaid.svg
    :target: https://travis-ci.org/sunscrapers/django-getpaid
.. image:: https://img.shields.io/coveralls/github/cypreess/django-getpaid.svg
    :target: https://coveralls.io/github/django-getpaid/django-getpaid?branch=master
.. image:: https://img.shields.io/pypi/wheel/django-getpaid.svg
    :target: https://pypi.org/project/django-getpaid/
.. image:: https://img.shields.io/pypi/l/django-getpaid.svg
    :target: https://pypi.org/project/django-getpaid/


django-getpaid is a multi-broker payment processor for Django

Documentation
=============

The full documentation is at https://django-getpaid.readthedocs.io.

Features
========

* support for multiple payment brokers at the same time
* clean but flexible architecture
* support for asynchronous status updates - both push and pull
* support for modern REST-based broker APIs
* support for multiple currencies (but one per payment)
* easy customization with provided base abstract models and swappable mechanic (same as with Django's User model)


Quickstart
==========

Install django-getpaid and at least one payment backend:

.. code-block:: console

    pip install django-getpaid
    pip install django-getpaid-paynow

Add them to your ``INSTALLED_APPS``:

.. code-block:: python

    INSTALLED_APPS = [
        ...
        'getpaid',
        'getpaid_paynow',  # one of plugins
        ...
    ]

Add getpaid to URL patterns:

.. code-block:: python

    urlpatterns = [
        ...
        path('payments/', include('getpaid.urls')),
        ...
    ]

Use ``getpaid.models.AbstractOrder`` as parent class of your Order model and define minimal set of methods:

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

        def get_user_info(self):
            return {"email": self.buyer.email}

        def get_description(self):
            return self.description


Inform getpaid of your Order model in ``settings.py`` and provide settings for payment backends:

.. code-block:: python

    GETPAID_ORDER_MODEL = 'yourapp.MyCustomOrder'

    GETPAID_BACKEND_SETTINGS = {
        'getpaid_paynow': {   # dotted import path of the plugin
            # refer to backend docs for its real settings
            "api_key": "9bcdead5-b194-4eb5-a1d5-c1654572e624",
            "signature_key": "54d22fdb-2a8b-4711-a2e9-0e69a2a91189",
        },
    }

And... provide some business logic ;)

Your pre-payment view should use ``getpaid.forms.PaymentMethodForm`` `bound <https://docs.djangoproject.com/en/3.0/ref/forms/api/#ref-forms-api-bound-unbound>`_
with payment data. During binding the form will generate a list of plugins
(payment methods) supporting your currency and hide rest of the fields.
Then this form should be POSTed to ``{% url 'getpaid:create-payment' %}`` to create
new payment. You should be automatically redirected to paywall. After payment
you should by default return to order-detail page but this behavior can be
changed by plugin's config.

Running Tests
=============

Does the code actually work?

.. code-block:: console

    poetry install
    poetry run tox


Credits
=======

Created by `Krzysztof Dorosz <https://github.com/cypreess>`_.
Redesigned and rewritten by `Dominik Kozaczko <https://github.com/dekoza>`_.

Proudly sponsored by `SUNSCRAPERS <http://sunscrapers.com/>`_

Tools used in rendering this package:

*  Cookiecutter_
*  `cookiecutter-djangopackage`_

.. _Cookiecutter: https://github.com/audreyr/cookiecutter
.. _`cookiecutter-djangopackage`: https://github.com/pydanny/cookiecutter-djangopackage


Disclaimer
==========

This project has nothing in common with `getpaid <http://code.google.com/p/getpaid/>`_ plone project.
