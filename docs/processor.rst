==================================
Writing your own payment processor
==================================

.. py:currentmodule:: getpaid.processor

You can start by using `cookiecutter`_ to bootstrap your plugin::

    $ cookiecutter gh:django-getpaid/cookiecutter-getpaid-backend

After answering some basic questions you will have a boilerplate ready.
You now should edit ``PaymentProcessor`` located in ``yourproject/processor.py``.
You should **not** change the class name but if you do, you also have to change
``apps.py`` so that the ``registry.register()`` method gets your class as param.

PaymentProcessor API
====================

.. autoclass:: BaseProcessor
   :members:


.. _cookiecutter: https://cookiecutter.readthedocs.io/
