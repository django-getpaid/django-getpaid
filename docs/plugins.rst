========================
Creating payment plugins
========================
.. py:currentmodule:: getpaid.processor

In order to create a plugin for a payment broker, first you need to
write a subclass of :class:`BaseProcessor` named ``PaymentProcessor``
and place it in ``processor.py`` in your app.

The only method you have to provide is :py:meth:`~getpaid.processor.BaseProcessor.prepare_transaction`
that needs to return a :class:`~django.http.HttpResponse` subclass (eg. HttpResponseRedirect or TemplateResponse).
The use of all other methods depends directly on how the paywall operates.

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
