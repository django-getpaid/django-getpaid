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

Quickstart
==========

Install django-getpaid and a payment backend:

.. code-block:: console

    pip install django-getpaid
    pip install django-getpaid-dotpay

Add them to your ``INSTALLED_APPS``:

.. code-block:: python

    INSTALLED_APPS = [
        ...
        'getpaid',
        'getpaid_dotpay',
        ...
    ]

Add django-getpaid's URL patterns:

.. code-block:: python

    urlpatterns = [
        ...
        url(r'^payments/', include('getpaid.urls')),
        ...
    ]

Use ``getpaid.models.AbstractOrder`` as parent class of your Order model and define minimal set of methods:

.. code-block:: python

    from getpaid.models import AbstractOrder

    class MyCustomOrder(AbstractOrder):
        # fields
        def get_absolute_url(self):
            return reverse('order-detail', kwargs=dict(pk=self.pk))

        def get_total_amount(self):
            return self.amount

        def get_user_info(self):
            return dict(email=self.buyer.email)

        def get_description(self):
            return self.description


Select your Order model in ``settings.py`` and provide settings for payment backends:

.. code-block:: python

    GETPAID_ORDER_MODEL = 'yourapp.MyCustomOrder'

    GETPAID_BACKEND_SETTINGS = {
        'getpaid_dotpay': {   # dotted import path of the plugin
            # refer to backend docs for its real settings
            'merchant_id': 123456789,
            'key2': abcdef123456789,
        },
    }


Features
========

* support for multiple payment brokers at the same time
* clean but flexible architecture
* support for asynchronous status updates - both push and pull
* support for using multiple currencies (but one per payment)
* easy customization with provided base abstract models and swappable mechanic (same as with Django's User model)


Running Tests
=============

Does the code actually work?

::

    source <YOURVIRTUALENV>/bin/activate
    (myenv) $ pip install tox
    (myenv) $ tox -p all



Disclaimer
==========

This project has nothing in common with `getpaid <http://code.google.com/p/getpaid/>`_ plone project.


Credits
=======

Proudly sponsored by `SUNSCRAPERS <http://sunscrapers.com/>`_

Tools used in rendering this package:

*  Cookiecutter_
*  `cookiecutter-djangopackage`_

.. _Cookiecutter: https://github.com/audreyr/cookiecutter
.. _`cookiecutter-djangopackage`: https://github.com/pydanny/cookiecutter-djangopackage
