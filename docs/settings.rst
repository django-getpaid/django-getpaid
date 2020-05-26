========
Settings
========

.. contents::
    :local:
    :depth: 1


Core settings
=============


``GETPAID_ORDER_MODEL``
-----------------------

No default, you **must** provide this setting.

The model to represent an Order. See :doc:`customization`.

.. warning::
    You cannot change the ``GETPAID_ORDER_MODEL`` setting during the lifetime of
    a project (i.e. once you have made and migrated models that depend on it)
    without serious effort. It is intended to be set at the project start,
    and the model it refers to must be available in the first migration of
    the app that it lives in.

``GETPAID_PAYMENT_MODEL``
-------------------------

Default: ``'getpaid.Payment'``

The model to represent a Payment. See :doc:`customization`.

.. warning::
    You cannot change the ``GETPAID_PAYMENT_MODEL`` setting during the lifetime of
    a project (i.e. once you have made and migrated models that depend on it)
    without serious effort. It is intended to be set at the project start,
    and the model it refers to must be available in the first migration of
    the app that it lives in.

Backend settings
================

To provide configuration for payment backends, place them inside ``GETPAID_BACKEND_SETTINGS``
dictionary. Use plugin's dotted path - just as you put it in  ``INSTALLED_APPS``
- as a key for the config dict. See this example::

    GETPAID_BACKEND_SETTINGS = {
        "getpaid.backends.dummy": {
            "use_sandbox": True,
            "confirmation_method": "push",
            "gateway": reverse_lazy("paywall:gateway"),
        },
        "getpaid_payu": {
            "use_sandbox": True,
            # take these from your merchant panel:
            "pos_id": 12345,
            "second_key": "91ae651578c5b5aa93f2d38a9be8ce11",
            "oauth_id": 12345,
            "oauth_secret": "12f071174cb7eb79d4aac5bc2f07563f"
            "continue_url": "{frontend_url}platnosci/{payment_id}/koniec/",
        }
    }


Each backend defines its own settings this way. Please check the backend's documentation.


Optional settings
=================

A place for optional settings is ``GETPAID`` dictionary, empty by default.
It can contain these keys:

``POST_TEMPLATE``
-----------------

Default: None

This setting is used by processor's default :meth:`~getpaid.processor.BaseProcessor.get_template_names`
method to override backend's :attr:`~getpaid.processor.BaseProcessor.template_name`.
The template is used to render that backend's POST form.
This setting can be used to provide a global default for such cases if you use more
plugins requiring such template. You can also use ``POST_TEMPLATE`` key in
:ref:`backend's config<Backend settings>` to override the template just for one backend.


``POST_FORM_CLASS``
-------------------

Default: None

This setting is used by backends that use POST flow.
This setting can be used to provide a global default for such cases if you use more
plugins requiring such template. You can also use ``POST_FORM_CLASS`` key in
:ref:`backend's config<Backend settings>` to override the template just for one backend.
Use full dotted path name.


``SUCCESS_URL``
---------------

Default: ``"getpaid:payment-success"``

Allows setting custom view name for successful returns from paywall.
Again, this can also be set on a per-backend basis.

If the view requires kwargs to be resolved, you need to override

``FAILURE_URL``
---------------

Default: ``"getpaid:payment-failure"``

Allows setting custom view name for fail returns from paywall.
Again, this can also be set on a per-backend basis.

``HIDE_LONELY_PLUGIN``
----------------------

Default: False

Allows you to hide plugin selection if only one plugin would be presented.
The hidden plugin will be chosen as default.

``VALIDATORS``
--------------

Default: []

Here you can provide import paths for validators that will be run against
the payment before it is sent to the paywall. This can also be set on a
per-backend basis.
