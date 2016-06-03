Writing custom payment backend
==============================

**django-getpaid** allows you to use two types of custom backends: internal and third-party backends. There is no architectural difference between them, only the first one is shipped with django-getpaid code, while the second one can be maintained separately. However if you are going to provide a payment backend to any popular payment method (even if it's only popular in your country) you are very welcome to contribute your backend to django-getpaid. Some hints how to do that are described in :doc:`index` "Developing" section.

Creating initial backend application
------------------------------------

All payment backends are standalone django apps. You can easily create one using ``django-admin.py`` tool::

    $ django-admin.py startapp mybackend


Before using this app as a legal django-getpaid backend, you need to follow a few more steps described below.

Creating ``PaymentProcessor`` class
-----------------------------------

**Required**


``PaymentProcessor`` class is one of the most important parts of whole backend. All logic related to processing a payment should be put into this class. This class should derive from ``getpaid.backends.PaymentProcessorBase``.

.. autoclass:: getpaid.backends.PaymentProcessorBase
    :members:
    :undoc-members:

Your ``PaymentProcessor`` needs to be named exactly this way and can live anywhere in the code structure as long as it can be imported from the main scope. We recommend you to put this class directly into your app ``__init__.py`` file, as there is really no need to complicate it anymore by adding additional files.

Overriding ``get_gateway_url()`` method
---------------------------------------

**Required**


This is the most important method from the django-getpaid perspective. You need to override the ``get_gateway_url`` method, which is an entry point to your backend. This method is based on the ``request`` context and on the ``self.payment`` and should return the URL to the payment gateway that the client will be redirected to.

If your backend emits the ``getpaid.signals.user_data_query`` signal, please respect the convention below on which key names to expect as parameters. The objective is to make this signal as agnostic as possible to payment processors.

* email
* lang
* name
* address
* address_number
* address_complement
* address_quarter
* address_city
* address_state
* address_zip_code
* phone
* phone_area_code

Providing extra models
----------------------

**Required** (providing ``build_models()`` function)


Your application in most cases will not need to provide any models at all. In this situation it is very important to add following line in your ``models.py`` empty file::


    def build_models(payment_class):
        return []

The method ``build_models`` is required for every payment backend as it allows to dynamically build django models in run-time, that need to depend on ``Payment`` class but don't want to use ``content_type`` in django.

To do that you will need to use ``getpaid.abstract_mixin.AbstractMixin``, please refer to code. Here is just a simple example of a working dynamically created model to give you an idea of how it works::

    from django.db import models
    from getpaid.abstract_mixin import AbstractMixin

    class PaymentCommentFactory(models.Model, AbstractMixin):
        comment = models.CharField(max_length=100, default="a dummy transaction")

        class Meta:
            abstract = True

        @classmethod
        def contribute(cls, payment):
            return {'payment': models.OneToOneField(payment)}

    PaymentComment = None

    def build_models(payment_class):
        global PaymentComment
        class PaymentComment(PaymentCommentFactory.construct(payment_class)):
            pass
        return [PaymentComment]


This will create in run-time a model ``PaymentComment`` which has two fields: CharField ``comment`` and ForeignKey ``payment``. You can use it in your backend.

.. note::

    Obviously you can also provide static django models without using this fancy method, as all backend apps are also regular django apps!


Providing extra urls
--------------------

**Optional**


In most cases your backend will need to provide some additional urls - for example the url for accepting incoming request from payment gateways about status changes, etc. You can just add your URL definitions like in standard django app.

.. note::

    You don't need to register your backend's ``urls.py`` module with ``include()`` in your original project's ``urls.py``. All enabled applications will have theirs urls automatically appended, but they will be prefixed with backend full path.


For example, consider following case::

   from django.conf.urls import patterns, url
   from getpaid.backends.dummy.views import DummyAuthorizationView

   urlpatterns = patterns('',
       url(r'^payment/authorization/(?P<pk>[0-9]+)/$', DummyAuthorizationView.as_view(), name='getpaid:dummy:authorization'),
   )


This will expose a link that will point to something like: ``/getpaid.backends.dummy/payment/authorization/0/`` (of course ``getpaid.urls`` could be prefixed with some other path, then the whole path would also have some additional prefix e.g. ``/my/app/payments/getpaid.backends.dummy/payment/authorization/0/`` ). As you can see like in regular django app, you connect your urls with app views.

Providing extra views
---------------------

**Optional**


If you need to provide some views, please use standard ``views.py`` django convention. Class based views are welcome!

.. note::

    It is highly recommended to manage all payment logic in additional methods of ``PaymentProcessor`` class. Let the view only be a wrapper for preparing arguments for one ``PaymentProcessor`` logic method. In this way you will keep all payment processing related logic in one place.

.. warning::

    When using any kind of POST views that accepts external connections remember to use ``@csrf_exempt`` decorator, as django by default will 403 Forbid those connections.

Asynchronous tasks
------------------

**Optional**

django-getpaid is highly recommending using django-celery for all asynchronous processing. If you need to do any, please create celery tasks with the ``@task()`` decorator.

.. note::

    Just like what we have done with the view, when processing celery tasks it is recommended to put your business logic in the class ``PaymentProcessor``. Let the task function only be a wrapper for preparing arguments for one ``PaymentProcessor`` logic method.


Configuration management script
-------------------------------

**Optional**


If your module need to generate any kind of configuration data (for example links that you should provide in payment broker configuration site) you should create a django management script that displays all needed information (e.g. displaying links using django ``reverse()`` function). By the convention you should name this management script in format: ``<short backend name>_configuration.py`` (e.g. ``payu_configuration.py``).
