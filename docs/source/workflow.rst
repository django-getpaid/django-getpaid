Payment workflow integration
============================

With few simple steps you will easily integrate your project with django-getpaid. This module is shipped with very well documented django-getpaid test project which can be found with module source code. Please refer to this code for implementation details.


Connect urls
------------

**Required**

Add to your urls::

        url(r'', include('getpaid.urls')),




Prepare your order model
------------------------

**Required**

First of all you need a model that will represent an order in you application. It does not matter how complicated the model is or what fields it provides, is it single item order, or multiple items order. Let's take an example from test project::

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

    getpaid.register_to_payment(Order, unique=False, related_name='payments')


First of all class name is not important at all. You register a model with ``register_to_payment`` method.

.. autofunction:: getpaid.register_to_payment

You can add some `kwargs` that are basically used for ``ForeignKey`` kwargs. In this example whe allow of creating multiple payments for one order, and naming One-To-Many relation.

There are two important things on that model. In fact two methods are required to be present in order class. The first one is ``__unicode__`` method as this will be used in few places as a fallback for generating order description. The second one is ``get_absolute_url`` method which should return an URL of order object. It is used again as a fallback for some final redirections after payment success of failure (if you do not provide otherwise).

The second important thing that it actually don't mather if you even store `total` in database, or just can sum it up from some items. You will see why, in further sections.

.. warning::

    Remember to run ``./manage.py syncdb`` in order to create additional Database tables.



Controlling payment creation for an order
`````````````````````````````````````````

Getpaid supports payment creation policy for order. It means that yours order class can implement a method ``is_ready_for_payment()`` which will inform getpaid if creation of a payment for the given order is allowed. This is a typical situation if e.g. you want to disallow to make another payment for an order that status is "already paid" or that is expired by now. If you do not implement this method, getpaid will assume that payment is always allowed.


Prepare payment form for order
------------------------------

**Required**

Your application after some custom workflow just created an order object. That's fine. We now want to get paid for that order. So lets take a look on a view for creating a payment for an order::

    from django.views.generic.detail import DetailView
    from getpaid.forms import PaymentMethodForm
    from getpaid_test_project.orders.models import Order

    class OrderView(DetailView):
        model=Order

        def get_context_data(self, **kwargs):
            context = super(OrderView, self).get_context_data(**kwargs)
            context['payment_form'] = PaymentMethodForm(self.object.currency, initial={'order': self.object})
            return context


Here we get a ``PaymentMethodForm`` object, that is parametrised with currency type. This is an important thing, because this form will display you only payments method that are suitable for a given order currency.

``PaymentMethodForm`` provides two fields: HiddenInput with order_id and ChoiceField with backend name. This is how you use it in template::

    <form action="{% url getpaid-new-payment currency=object.currency %}" method="post">
        {% csrf_token %}
        {{ payment_form.as_p }}
        <input type="submit" value="Continue">
    </form>


Action URL of form should point on named link  `getpaid-new-payment` that requires currency code argument. This form will redirect client from order view directly to page of payment broker.

Filling necessary payment data
------------------------------

**Required**

Because the idea of whole module is that it should be loosely coupled, there is this convention that it does not require any structure of your order model. But still it need to know some transaction details of your order. For that django signals is used. djang-getpaid while generating gateway redirect url will emit to your application a ``getpaid.signals.new_payment_query`` signal. Here is the signal declaration::

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


So this is a little piece of logic that you need to provide to map your order to payment object. As you can see you can do all fancy stuff here to get order total value and currency code.

.. note::

    If you don't know where to put your listeners code, we recommend to put it in ``listeners.py`` file and then add a line ``import listeners`` to the end of you ``models.py`` file. Both files (``listeners.py`` and ``models.py``) should be placed in on of your app (possibly an app related to order model).

Handling changes of payment status
----------------------------------

**Required**

Signals are also used to inform you that some particular payment just change status. In this case you will use ``getpaid.signals.payment_status_changed`` signal which is defined as::

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

For example when payment changes status from any non 'paid' to 'paid' status, that means that all necessary amount was verified by your payment broker. You can now access ``payment.order`` object and do some stuff here.

Handling new payment creation
-----------------------------

**Optional**

For some reasons (e.g. for KPI benchmarking) it can be important to you how many and which payments were made. For that reason you can handle ``getpaid.signals.new_payment`` signal defined as::

    new_payment = Signal(providing_args=['order', 'payment'])
    new_payment.__doc__ = """Sent after creating new payment."""


.. note::

    This method will enable you to make on-line KPI processing. For batch processing you can just query a database for Payment model as well.

Setup your payment backends
---------------------------

**Required**

Please be sure to read carefully section :doc:`backends` for information of how to configure particular backends. They will probably not work out of the box without providing some account keys or other credentials.