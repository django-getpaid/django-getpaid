============
Installation
============

This document presents the minimal steps required to use ``django-getpaid`` in your project.


Get it from PyPI
----------------

    $ pip install django-getpaid

We do not recommend using development version as it may contain bugs.


Plugins installation
--------------------

There should be several plugins available in our repo. Each follow this schema: ``django-getpaid-<backend_name>``
For example if you want to install PayU integration, run::

    $ pip install django-getpaid-payu


Enabling django application
---------------------------

Next, add ``'getpaid'`` and any plugin to ``INSTALLED_APPS`` in your ``settings.py``.
Plugins have the format ``getpaid_<backend_name>``::

    INSTALLED_APPS = [
        # ...
        "getpaid",
        "getpaid_payu",
    ]



Creating Order model
--------------------

The model does not need to be named ``Order`` - you may choose any name you want.
The important thing though is for it to inherit ``getpaid``'s ``AbstractOrder``
and implement some of its methods. An example Order could look like this::

    from django.conf import settings
    from django.db import models
    from getpaid.models import AbstractOrder

    class CustomOrder(AbstractOrder):
        buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
        description = models.CharField(max_length=128, default='Order from mystore')
        total = models.DecimalField()
        currency = models.CharField(max_length=3, default=settings.DEFAULT_CURRENCY)

        def get_user_info(self):
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
            # after returning from the broker page and you can use `success` param
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

Tell ``getpaid`` what model handles orders
------------------------------------------

Put this inside your ``settings.py``::

    GETPAID_ORDER_MODEL = "yourapp.CustomOrder"


(Optional) Provide custom Payment model
---------------------------------------

If you want, you can provide your own Payment model. Read more in :doc:`customization`

.. note::

    Payment model behaves like django.auth.User model - after you use the original,
    migration to a custom version is VERY hard.

Add getpaid to urls
-------------------

.. code-block::

    urlpatterns = [
        # ...
        path("payments", include("getpaid.urls")),
    ]


Provide config for plugins
--------------------------

The last step is to provide config for installed plugins inside your ``settings.py``::

    GETPAID_BACKEND_SETTINGS = {
        "getpaid_payu": {   # dotted import path of the plugin
            # refer to backend docs for its real settings
            "pos_id": "123456789",
            "key2": "abcdef123456789",
        },
        "getpaid.backends.dummy": {
            "confirmation_method": "push",
            },
    }
