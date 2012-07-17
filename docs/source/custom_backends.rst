Writing custom payment backend
==============================

**django-getpaid** allows to use two types of custom backends: internal and third-party backends. There is no architectural difference between them, only the first one is shipped with django-getpaid code, while the second one can be maintained separately. However if you are going to provide payment backend to any popular payment method (in your country) you are very welcome to contribute you backend to django-getpaid. Some hints how to do that are described in :doc:`contributors` section.

Creating initial backend application
------------------------------------

All payment backends are standalone django apps. You can easily create one using ``django-admin.py`` tool::

    $ django-admin.py startapp mybackend


Before you can use this app as a legal django-getpaid backend you need to follow few more steps.

Creating ``PaymentProcessor`` class
-----------------------------------

**Required**


``PaymentProcessor`` class is one of the most important part of whole backend. All logic related to processing a payment should be put into this class. This class should derive from ``getpaid.backends.PaymentProcessorBase``.

.. autoclass:: getpaid.backends.PaymentProcessorBase
    :members:
    :undoc-members:

Your ``PaymentProcessor`` need to be named exactly this way and can live anywhere in the code structure unless it could be imported from main scope. We recommend you to put this class directly into your app ``__init__.py`` file, as there is really no need to complicate structure more by adding additional file.

Overriding ``get_gateway_url()`` method
---------------------------------------

**Required**


The most important thing from django-getpaid perspective is to overide ``get_gateway_url`` method which is an entry point to your backend. This method base on ``request`` context and ``self.payment`` should return an URL that will redirect client directly to payment gateway.

Providing extra models
----------------------

**Required** (providing ``build_models()`` function)


Your application in most cases will not need to provide any models at all. In this situation it is very important to add following line in your ``models.py`` empty file::


    def build_models(payment_class):
        return []

Method ``build_models`` is required for every payment backend as it allows to dynamically build django models in run-time, that need to depend on ``Payment`` class but don't want to use ``content_type`` in django.

To do that you will need to use ``getpaid.abstract_mixin.AbstractMixin``, but please refer to code. Here is just simple example of working dynamically created model to give you some idea how is it working::

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


This will create in a run-time a model ``PaymentComment`` which has two fields: CharField ``comment`` and ForeignKey ``payment``. You can use it in your backend.

.. note::

    Obviously you can also provide static django models without using this fancy method, as all backend apps are also regular django apps!


Providing extra urls
--------------------

**Optional**


In most cases your backend will need to provide some additional urls - for example the url for accepting incoming request from payment gateways about status changes, etc. You can just add your URL definitions like in standard django app.

.. note::

    You don't need to register your backend's ``urls.py`` module with ``include()`` in your original project's ``urls.py``. All enabled applications will have theirs urls automatically appended, but they will be prefixed with backend full path. For example, consider following case::

       from django.conf.urls import patterns, url
       from getpaid.backends.dummy.views import DummyAuthorizationView

       urlpatterns = patterns('',
           url(r'^payment/authorization/(?P<pk>[0-9]+)/$', DummyAuthorizationView.as_view(), name='getpaid-dummy-authorization'),
       )

This will expose a link that will point to something like: ``/getpaid.backends.dummy/payment/authorization/0/`` (of course ``getpaid.urls`` could be prefixed with some other path, then the whole path would also have some additional prefix e.g. ``/my/app/payments/getpaid.backends.dummy/payment/authorization/0/`` ). As you can see like in regular django app you connect your urls with app views.

Providing extra views
---------------------

**Optional**


If you need to provide some views, please use standard ``views.py`` django convention. Class based views are welcome!

.. note::

    It is highly recommended to manage all payment logic in additional methods of ``PaymentProcessor`` class. Let the view will be only a wrapper for preparing arguments for one ``PaymentProcessor`` logic method. In this way you will keep all payment processing related logic in one place.

.. warning::

    When using any kind of POST views that accepts external connections remember to use ``@csrf_exempt`` decorator, as django by default will 403 Forbid those connections.

Asynchronous tasks
------------------

**Optional**

django-getpaid is highly recommending using django-celery for all asynchronous processing. If you need to do any, please create celery tasks with ``@task()`` decorator.

.. note::

    As with view, when processing celery task please put or your business logic into one of ``PaymentProcessor`` method. Let the task function be only a wrapper for preparing arguments for one ``PaymentProcessor`` logic method.


Configuration management script
-------------------------------

**Optional**


If your module need to generate any kind of configuration data (for example links that you should provide in payment broker configuration site) you should create a django management script that displays all needed information (e.g. displaying links using django ``reverse()`` function). By the convention you should name this management script in format: ``<short backend name>_configuration.py`` (e.g. ``payu_configuration.py``).