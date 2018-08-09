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

``GETPAID_BACKEND_SETTINGS``
----------------------------

Default: ``{}`` (Empty dictionary)

A dictionary containing the settings for getpaid's backends. Keys in this dictionary
are the dotted paths to each backend - just as you put them in ``INSTALLED_APPS``.

Each backend defines its own settings there. Please check the backend's documentation.
There is one exception - each backend can provide ``POST_TEMPLATE`` setting which
takes precedence over ``GETPAID_POST_TEMPLATE`` described below. This setting is
used by processor's default ``get_template_names`` method to override backend's
``template_name`` attribute that points to a template that is used to render that
backend's POST form. As this method is rarely used, you'll probably never want
to use it anyway.


Optional settings
=================

``GETPAID_POST_TEMPLATE``
-------------------------

Default: None

This setting is used processor's by default ``get_template_names`` method to
override backend's ``template_name`` attribute that points to a template that is
used to render that backend's POST form. As this method is rarely used, you'll
probably never want to use it anyway.
