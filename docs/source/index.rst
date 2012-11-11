.. django-getpaid documentation master file, created by
   sphinx-quickstart on Mon Jul 16 21:16:46 2012.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to django-getpaid's documentation!
==========================================

**django-getpaid** is carefully designed multi-broker payment processor for django applications. The main advantages of this django application is:
 * instead of only one payment broker, you can use **multiple payment brokers** in your application, what is wise considering ane single payment broker downtime,
 * payment brokers have a **flexible architecture** each one based on a django application structure (they can introduce own logic, views, urls, models),
 * support to **asynchronous** payment status change workflow (which is required by most brokers and is architecturally correct for production use),
 * support for **multiple payments currency** at the same time,
 * uses just a **minimal assumption** on your code, that you will have any kind of order model class.

The basic usage is to connect you order model class with `django-getpaid`. Because of using advanced `AbstractMixin`, Payment model class uses real ``ForeignKey`` to your order class model, so it avoids messy django ``content_type`` relations.

This app was written because still there is not a single reliable or simple to use payment processor. There are many  payments related projects out there like `Satchmo <http://satchmoproject.sadba.org/docs/dev/>`_, `python-payflowpro <https://github.com/bkeating/python-payflowpro/>`_, `django-authorizenet <https://github.com/zen4ever/django-authorizenet>`_, `mamona <https://github.com/emesik/mamona>`_, `django-paypal <https://github.com/johnboxall/django-paypal>`_, `django-payme <https://github.com/bradleyayers/django-payme/>`_, but none of them are satisfying. `Mamona` project was the most interesting payment app out there (because of general conception), but still has got some serious architectural pitfalls. Therefore `django-getpaid` in the basic stage was aimed to be a next version of `mamona`. Unfortunately plenty of architectural decisions of `mamona` author caused, that `django-getpaid` has been started as a separate project, while still borrowing a lot of great ideas from `mamona`, like e.g. using `AbstractMixin`, dynamic model and urls loading, etc. Thanks `mamona`!



**Disclaimer:** this project has nothing in common with `getpaid <http://code.google.com/p/getpaid/>`_ plone project. It is mostly based on `mamona <https://github.com/emesik/mamona>`_ project.

Contents:
=========

.. toctree::
   :maxdepth: 2

   installation
   workflow
   backends
   custom_backends
   south
   contributors


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

