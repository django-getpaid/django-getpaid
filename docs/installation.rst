============================
Installation & Configuration
============================

This document presents the minimal steps required to use ``django-getpaid`` in your project.


Get it from PyPI
----------------

.. code-block:: shell

    pip install django-getpaid

We do not recommend using development version as it may contain bugs.


Install at least one plugin
---------------------------

There should be several plugins available in our repo. Each follows this
schema: ``django-getpaid-<backend_name>``
For example if you want to install PayU integration, run:

.. code-block:: shell

    pip install django-getpaid-payu


Create Order model
------------------

You need to create your own model for an order. It should inherit from
``getpaid.abstracts.AbstractOrder`` (if not, it must implement its methods)
and you need to implement some methods. It could look like this example:

.. code-block:: python

    from django.conf import settings
    from django.db import models
    from getpaid.abstracts import AbstractOrder

    class CustomOrder(AbstractOrder):
        buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
        description = models.CharField(max_length=128, default='Order from mystore')
        total = models.DecimalField()
        currency = models.CharField(max_length=3, default=settings.DEFAULT_CURRENCY)

        def get_buyer_info(self):
            return {"email": self.buyer.email}

        def get_total_amount(self):
            return self.total

        def get_description(self):
            return self.description

        def get_currency(self):
            return self.currency

        # either one of those two is required:
        def get_redirect_url(self, *args, success=None, **kwargs):
            # this method will be called to get the url that will be displayed
            # after returning from the paywall page and you can use `success` param
            # to differentiate the behavior in case the backend supports it.
            # By default it returns this:
            return self.get_absolute_url()

        def get_absolute_url(self):
            # This is a standard method recommended in Django documentation.
            # It should return an URL with order details. Here's an example:
            return reverse("order-detail", kwargs={"pk": self.pk})

        # these are optional:
        def is_ready_for_payment(self):
            # Most of the validation will be handled by the form
            # but if you need any extra logic beyond that, you can write it here.
            # This is the default implementation:
            return True

        def get_items(self):
            # Some backends expect you to provide the list of items.
            # This is the default implementation:
            return [{
                "name": self.get_description(),
                "quantity": 1,
                "unit_price": self.get_total_amount(),
            }]


Make migration for your custom model
------------------------------------


Run ``manage.py makemigrations`` because ``getpaid`` will need that to initialize properly.


Tell ``getpaid`` what model handles the orders
----------------------------------------------

Put this inside your ``settings.py``::

    GETPAID_ORDER_MODEL = "yourapp.CustomOrder"



Enable app and plugin
---------------------

Next, add ``"getpaid"`` and the plugin to ``INSTALLED_APPS`` in your ``settings.py``.
Plugins have the format ``getpaid_<backend_name>``:

.. code-block:: python

    INSTALLED_APPS = [
        # ...
        "getpaid",
        "getpaid_payu",
    ]

(Optional) Provide custom Payment model
---------------------------------------

If you want, you can provide your own Payment model. Read more in :doc:`customization`.

.. note::

    Payment model behaves like django.auth.User model - after you use the original,
    migration to a custom version is quite hard.


Migrate
-------

Run ``manage.py migrate`` to reflect models onto database.



Add getpaid to urls
-------------------

.. code-block:: python

    urlpatterns = [
        # ...
        path("payments", include("getpaid.urls")),
    ]


Provide config for plugins
--------------------------

For each installed plugin you can configure it in ``settings.py``:

.. code-block:: python

    GETPAID = {
        "BACKENDS":{
            "getpaid_payu": {   # dotted import path of the plugin
                # refer to backend docs and take these from your merchant panel:
                "pos_id": 12345,
                "second_key": "91ae651578c5b5aa93f2d38a9be8ce11",
                "client_id": 12345,
                "client_secret": "12f071174cb7eb79d4aac5bc2f07563f",
            },

            # this plugin is meant only for testing purposes
            "getpaid.backends.dummy": {
                "confirmation_method": "push",
            },
        }
    }


Prepare views and business logic
--------------------------------

The logic for building an order is up to you. You can eg. use a cart application
to gather all Items for your Order.

An example view and its hookup to urls.py can look like this::

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
Here's the important part::

    <h2>Choose payment broker:</h2>
    <form action="{% url 'getpaid:create-payment' %}" method="post">
      {% csrf_token %}
      {{ payment_form.as_p }}
      <input type="submit" value="Checkout">
    </form>

And that's pretty much it.

After you open order detail you should see a list of plugins supporting your currency
and a "Checkout" button that will redirect you to selected paywall. After completing
the payment, you will return to the same view.

Please see fully working `example app`_.

Next steps
----------

If you're not satisfied with provided Payment model or the
PaymentMethodForm, please see :doc:`customization docs<customization>`.

.. _example app: https://github.com/django-getpaid/django-getpaid/tree/master/example
