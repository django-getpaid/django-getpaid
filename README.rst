
Welcome to django-getpaid!
============================

.. image:: https://img.shields.io/pypi/v/django-getpaid.svg
    :target: https://pypi.python.org/pypi/django-getpaid
    :alt: Latest PyPI version
.. image:: https://img.shields.io/pypi/dm/django-getpaid.svg
    :target: https://pypi.python.org/pypi/django-getpaid
    :alt: Number of PyPI downloads
.. image:: https://travis-ci.org/cypreess/django-getpaid.png?branch=master
    :target: https://travis-ci.org/cypreess/django-getpaid
.. image:: https://coveralls.io/repos/cypreess/django-getpaid/badge.svg?branch=master&service=github
    :target: https://coveralls.io/github/cypreess/django-getpaid?branch=master
.. image:: https://img.shields.io/badge/wheel-yes-green.svg
    :target: https://pypi.python.org/pypi/django-getpaid
.. image:: https://img.shields.io/pypi/l/django-getpaid.svg
    :target: https://pypi.python.org/pypi/django-getpaid
.. image:: https://d2weczhvl823v0.cloudfront.net/cypreess/django-getpaid/trend.png
    :target: https://bitdeli.com/free
   
Documentation: http://django-getpaid.readthedocs.org/en/latest/

**django-getpaid** is carefully designed **multi-broker payment processor for Django** framework. It was designed
to provide following features:

* **multiple payment brokers support** - allows using simultaneously many payments methods at the same time,
* **multiple payments currency support** (getpaid will automatically filter available backends list accordingly to the payment currency),
* **integration flexibility**  -  makes minimal assumption on 3rd party code - requires only an existence of any single django model representing an order,
* **proper architecture design** - all backends which requires fetching payment confirmation are enforced to use asynchronous celery tasks.


Supported backends:
-------------------

In alphabetical order:

* `Dotpay.pl/Dotpay.eu <http://dotpay.eu>`_
* `Epay.dk <http://www.epay.dk>`_
* `Moip.com.br <http://moip.com.br>`_
* `PayU.pl <http://payu.pl>`_
* `Paymill.com <http://paymill.com>`_
* `Przelewy24.pl <http://www.przelewy24.pl/>`_
* `Transferuj.pl <http://transferuj.pl>`_

Don't see the payment backend you need? `Writing your own backend <https://django-getpaid.readthedocs.org/en/latest/custom_backends.html>`_ is very simple. Pull requests are welcome.

Disclaimer
----------
This project has nothing in common with `getpaid <http://code.google.com/p/getpaid/>`_ plone project.
It is mostly based on `mamona <https://github.com/emesik/mamona>`_ project.
This app was written because there was not a single reliable or simple to use payment processor dedicated to django.
You can refer to other payment modules which does not meet our needs:
`Satchmo <http://satchmoproject.sadba.org/docs/dev/>`_,
`python-payflowpro <https://github.com/bkeating/python-payflowpro/>`_,
`django-authorizenet <https://github.com/zen4ever/django-authorizenet>`_,
`mamona <https://github.com/emesik/mamona>`_,
`django-paypal <https://github.com/johnboxall/django-paypal>`_,
`django-payme <https://github.com/bradleyayers/django-payme/>`_.



Payment workflow integration
============================

With few simple steps you will easily integrate your project with django-getpaid. This module is shipped with
very well documented django-getpaid test project which can be found with module source code. Please refer to this
code for implementation details.

Step 1. Prepare your order model
--------------------------------

**Required**

First of all you need a model that will represent an order in you application. It does not matter how
complicated the model is or what fields does it provide, be it single item order, or multiple items order.
Let's take an example from test project::

    from django.core.urlresolvers import reverse
    from django.db import models
    import getpaid

    class Order(models.Model):
        name = models.CharField(max_length=100)
        total = models.DecimalField(decimal_places=2, max_digits=8, default=0)
        currency = models.CharField(max_length=3, default='EUR')
        status = models.CharField(max_length=1, blank=True, default='W', choices=(('W', 'Waiting for payment'),
                                                                                   ('P', 'Payment complete')))
        def get_absolute_url(self):
            return reverse('order_detail', kwargs={'pk': self.pk})

        def __unicode__(self):
            return self.name

    Payment = getpaid.register_to_payment(Order, unique=False, related_name='payments')
    

and add the following line to your settings:

    GETPAID_ORDER_MODEL = 'my_super_app.Order'


First of all, class name is not important at all. You register a model with ``register_to_payment`` method.

You can add some `kwargs` that are basically used for ``ForeignKey`` kwargs. In this example whe allow creating multiple payments for one order, and naming One-To-Many relation.

There are two important things on that model. In fact two methods are required to be present in order class.
The first one is ``__unicode__`` method as this will be used in few places as a fallback for generating
order description. The second one is ``get_absolute_url`` method which should return an URL of order object.
It is used again as a fallback for some final redirections after payment success of failure (if you do not provide otherwise).

The second important thing is, that it actually doesn't matter if you store `total` in database or just sum it up from some items.
You will see why, in further sections.


Step 2. Prepare payment form for order
--------------------------------------

**Required**

Your application - after some custom workflow - just created an order object. That's fine.
We now want to get paid for that order. So lets take a look on a view for creating a payment for an order::

    from django.views.generic.detail import DetailView
    from getpaid.forms import PaymentMethodForm
    from getpaid_test_project.orders.models import Order

    class OrderView(DetailView):
        model=Order

        def get_context_data(self, **kwargs):
            context = super(OrderView, self).get_context_data(**kwargs)
            context['payment_form'] = PaymentMethodForm(self.object.currency, initial={'order': self.object})
            return context


Here we get a ``PaymentMethodForm`` object, that is parametrised with currency type.
This is an important thing, because this form will display you only payments method that are suitable
for a given order currency.

``PaymentMethodForm`` provides two fields: HiddenInput with order_id and ChoiceField with backend name. This is how you use it in template::

    <form action="{% url 'getpaid:new-payment' currency=object.currency %}" method="post">
        {% csrf_token %}
        {{ payment_form.as_p }}
        <input type="submit" value="Continue">
    </form>


Action URL of form should point on named link  `getpaid:new-payment` that requires currency code argument.
This form will redirect client from order view directly to page of payment broker.

Step 3. Filling necessary payment data
--------------------------------------

**Required**

Because the idea of whole module is that it should be loosely coupled, there is this convention that it does
not require any structure of your order model. But still it needs to know some transaction details of your order.
Django signals are used for that. django-getpaid, while generating gateway redirect url, will emit
a ``getpaid.signals.new_payment_query`` signal. Here is the signal declaration::

    new_payment_query = Signal(providing_args=['order', 'payment'])
    new_payment_query.__doc__ = """
    Sent to ask for filling Payment object with additional data:
        payment.amount:			total amount of an order
        payment.currency:		amount currency
    This data cannot be filled by ``getpaid`` because it is Order structure
    agnostic. After filling values just return. Saving is done outside signal.
    """

Your code should have some signal listeners, that will fill payment object with required information::

    from getpaid import signals

    def new_payment_query_listener(sender, order=None, payment=None, **kwargs):
        """
        Here we fill only two obligatory fields of payment, and leave signal handler
        """
        payment.amount = order.total
        payment.currency = order.currency

    signals.new_payment_query.connect(new_payment_query_listener)


So this is a little piece of logic that you need to provide to map your order to payment object.
As you can see you can do all fancy stuff here to get order total value and currency code.

.. note::

    If you don't know where to put your listeners code, we recommend to put it in ``listeners.py`` file
    and then add a line ``import listeners`` to the end of you ``models.py`` file. Both files
    (``listeners.py`` and ``models.py``) should be placed in on of your app (possibly an app related to order model).

Step 4. Handling changes of payment status
------------------------------------------

**Required**

Signals are also used to inform you that some particular payment just change status. In this case you will
use ``getpaid.signals.payment_status_changed`` signal which is defined as::

    payment_status_changed = Signal(providing_args=['old_status', 'new_status'])
    payment_status_changed.__doc__ = """Sent when Payment status changes."""

example code that handles status change::

    from getpaid import signals

    def payment_status_changed_listener(sender, instance, old_status, new_status, **kwargs):
        """
        Here we will actually do something, when payment is accepted.
        E.g. lets change an order status.
        """
        if old_status != 'paid' and new_status == 'paid':
            # Ensures that we process order only one
            instance.order.status = 'P'
            instance.order.save()

    signals.payment_status_changed.connect(payment_status_changed_listener)

For example: when payment changes status to 'paid', it means that the necessary amount was verified
by your payment broker. You can now access ``payment.order`` object and do some stuff here.

Step 5. Handling new payment creation
-------------------------------------

**Optional**

For some reasons you may want to make some additiona checks before a new
Payment is created or add some extra validation before the user is redirected
to gateway url. You can handle this with
``getpaid.signals.order_additional_validation`` signal defined as::

	order_additional_validation = Signal(providing_args=['request',
                                                         'order',
                                                         'backend'])
	order_additional_validation.__doc__ = """
	A hook for additional validation of an order.
	Sent after PaymentMethodForm is submitted but before
	Payment is created and before user is redirected to payment gateway.
	"""

It may also (e.g. for KPI benchmarking) be important for you to how many
and which payments were made.
You can handle ``getpaid.signals.new_payment`` signal defined as::

    new_payment = Signal(providing_args=['order', 'payment'])
    new_payment.__doc__ = """Sent after creating new payment."""


.. note::

    This method will enable you to make on-line KPI processing. For batch processing you can as well just query
    the database for Payment model.

Step 6. Setup your payment backends
-----------------------------------

**Required**

Please be sure to read carefully  `Backends <https://django-getpaid.readthedocs.org/en/latest/backends.html>`_ section for information on how to configure particular backends.
They will probably not work out of the box without providing some account keys or other credentials.
