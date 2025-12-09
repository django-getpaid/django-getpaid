.. image:: https://img.shields.io/pypi/v/django-getpaid.svg
    :target: https://pypi.org/project/django-getpaid/
    :alt: Latest PyPI version
.. image:: https://github.com/django-getpaid/django-getpaid/actions/workflows/run_tox.yml/badge.svg
    :target: https://github.com/django-getpaid/django-getpaid/actions/
.. image:: https://img.shields.io/pypi/wheel/django-getpaid.svg
    :target: https://pypi.org/project/django-getpaid/
.. image:: https://img.shields.io/pypi/l/django-getpaid.svg
    :target: https://pypi.org/project/django-getpaid/

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
    pip install django-getpaid-payu

Define an ``Order`` model by subclassing ``getpaid.abstracts.AbstractOrder``
and define some required methods:

.. code-block:: python

    from getpaid.abstracts import AbstractOrder

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

    GETPAID_BACKEND_SETTINGS = {
        "getpaid_payu": {
            # take these from your merchant panel:
            "pos_id": 12345,
            "second_key": "91ae651578c5b5aa93f2d38a9be8ce11",
            "oauth_id": 12345,
            "oauth_secret": "12f071174cb7eb79d4aac5bc2f07563f",
        },
    }

Create a migration for your model BEFORE adding ``getpaid`` to ``INSTALLED_APPS``:

.. code-block:: console

    ./manage.py makemigrations


Add ``getpaid`` and broker plugin to your ``INSTALLED_APPS``:

.. code-block:: python

    INSTALLED_APPS = [
        ...
        'getpaid',
        'getpaid_payu',  # one of plugins
        ...
    ]

Migrate the database:

.. code-block:: console

    ./manage.py migrate

Add getpaid to URL patterns:

.. code-block:: python

    urlpatterns = [
        ...
        path('payments/', include('getpaid.urls')),
        ...
    ]



Write a view that will create the Payment.

An example view and its hookup to urls.py can look like this:

.. code-block:: python

    # orders/views.py
    from getpaid.forms import PaymentMethodForm

    class OrderView(DetailView):
        model = Order

        def get_context_data(self, **kwargs):
            context = super(OrderView, self).get_context_data(**kwargs)
            context["payment_form"] = PaymentMethodForm(
                initial={"order": self.object, "currency": self.object.currency}
            )
            return context

    # main urls.py

    urlpatterns = [
        # ...
        path("order/<int:pk>/", OrderView.as_view(), name="order_detail"),
    ]

You'll also need a template (``order_detail.html`` in this case) for this view.
Here's the important part:

.. code-block::

    <h2>Choose payment broker:</h2>
    <form action="{% url 'getpaid:create-payment' %}" method="post">
        {% csrf_token %}
        {{ payment_form.as_p }}
        <input type="submit" value="Checkout">
    </form>


==================
Supported Versions
==================

The project currently targets Django 5.2 LTS as the baseline and is
continuously tested against Django 5.2, 5.3, 5.4 and 6.0 on Python 3.10–3.14.
Those combinations mirror the environments defined in ``tox.ini``.


Running Tests
=============

Install the project with the ``tests`` extra so pytest and friends are
available, then invoke tox:

.. code-block:: console

    poetry install -E tests
    poetry run tox
    # or run a specific environment, e.g. Django 5.2 on Python 3.13
    tox -e py313-django52


Alternatives
============

* `django-payments <https://github.com/mirumee/django-payments>`_


Credits
=======

Created by `Krzysztof Dorosz <https://github.com/cypreess>`_.
Redesigned and rewritten by `Dominik Kozaczko <https://github.com/dekoza>`_.


Development of version 2.0 sponsored by `SUNSCRAPERS <https://sunscrapers.com/>`_



Disclaimer
==========

This project has nothing in common with `getpaid <http://code.google.com/p/getpaid/>`_ plone project.
