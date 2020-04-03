========================
Creating payment plugins
========================
.. py:currentmodule:: getpaid.processor

In order to create a plugin for a payment broker, first you need
write a ``PaymentProcessor`` subclass of :class:`BaseProcessor`
and place it in ``processor.py`` in your app.

The only method you must to provide is :py:meth:`~BaseProcessor.get_paywall_params`
method that prepares a dict of values required by the paywall. All other methods
depend on the exact type of your payment provider and the flow they use.

To make your plugin available for the rest of the framework, you need to register it.
The most convenient way to do so is ``apps.py``:

.. code-block:: python

    from django.apps import AppConfig

    class MyPluginAppConfig(AppConfig):
        name = "getpaid_myplugin"
        verbose_name = "Some payment broker"

        def ready(self):
            from getpaid.registry import registry

            registry.register(self.module)

This way your plugin will be automatically registered after adding it to ``INSTALLED_APPS``.

Detailed API
============

.. autoclass:: BaseProcessor
   :members:
