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

Add them to your ``INSTALLED_APPS``:

.. code-block:: python

    INSTALLED_APPS = [
        ...
        'getpaid',
        'getpaid_payu',  # one of plugins
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

        def get_description(self):
            return self.description


Inform getpaid of your Order model in ``settings.py`` and provide settings for payment backends:

.. code-block:: python

    GETPAID_ORDER_MODEL = 'yourapp.MyCustomOrder'

    GETPAID_BACKEND_SETTINGS = {
        "getpaid_payu": {
            # take these from your merchant panel:
            "pos_id": 12345,
            "second_key": "91ae651578c5b5aa93f2d38a9be8ce11",
            "client_id": 12345,
            "client_secret": "12f071174cb7eb79d4aac5bc2f07563f",
        },
    }

Write a view that will create the Payment.

An example view and its hookup to urls.py can look like this:

.. code-block:: python

    # orders/views.py
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
