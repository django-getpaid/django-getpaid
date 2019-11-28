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


Optional settings
=================

``GETPAID_POST_TEMPLATE``
-------------------------

Default: None

This setting is used by processor's default ``get_template_names`` method to
override backend's ``template_name`` attribute. The template is used in backends
that use the POST form workflow which is quite rare. Refer to backend's
documentation to know if this is the case.

If you need to set the template on a per-backend basis, use ``POST_TEMPLATE``
setting for that backend's config in  ``GETPAID_POST_TEMPLATE`` dictionary.
The setting precedence is as follows: backend's ``POST_TEMPLATE`` setting ->
global ``GETPAID_POST_TEMPLATE`` setting -> backend's ``get_template_names``
method -> backend's default ``template_name`` attribute.
