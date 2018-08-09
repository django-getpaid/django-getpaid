Payment workflow integration
============================

With a few simple steps you will easily integrate your project with django-getpaid. This module is shipped with a very well documented django-getpaid test project which is packed together with the source code. Please refer to this code for implementation details.


Connect urls
------------

**Required**

Add to your urls::

        url(r'', include('getpaid.urls')),




Preparing your order model
--------------------------

**Required**

First of all you need a model that will represent an order in you application. It does not matter how complicated the model is or what fields it provides, if it is a single item order or multiple items order. You can also use a previously defined model you have, even if it's from a 3rd party app. Let's take an example from the test project::

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


For django 1.8 please add the following line to your settings:

    GETPAID_ORDER_MODEL = 'my_super_app.Order'


The class name is not important at all. Important is that you register your model using the ``register_to_payment`` method.

.. autofunction:: getpaid.register_to_payment

You can add some `kwargs` that are basically used for ``ForeignKey`` kwargs. In this example whe allow of creating multiple payments for one order, and naming One-To-Many relation.

There are two important things on that model. In fact two methods are required to be present in order class. The first one is ``__unicode__`` method as this will be used in few places as a fallback for generating order description. The second one is ``get_absolute_url`` method which should return the URL from the order object. It is used again as a fallback for some final redirections after payment success or failure (if you do not provide otherwise).

It is also important to note that it actually doesn't mather if you store the order `total` in database. You can also calculate it manually, for example by summing the price of all items. You will see how in further sections.

.. warning::

    Remember to run ``./manage.py syncdb`` in order to create additional database tables.



Controlling payment creation for an order
`````````````````````````````````````````

Getpaid supports payment creation policy for an order. It means that your order class can implement a method ``is_ready_for_payment()`` which will inform getpaid if the creation of a payment for the given order is allowed. This is a typical situation if e.g. you want to disallow to make another payment for an order that has the status "already paid" or that is expired by now. If you do not implement this method, getpaid will assume that paying this order is always allowed.


Preparing payment form for an order
-----------------------------------

**Required**

Your application after some custom workflow just created an order object. That's fine. We now want to get paid for that order. So let's take a look on a view for creating a payment for an order::

    from django.views.generic.detail import DetailView
    from getpaid.forms import PaymentMethodForm
    from example.orders.models import Order

    class OrderView(DetailView):
        model=Order

        def get_context_data(self, **kwargs):
            context = super(OrderView, self).get_context_data(**kwargs)
            context['payment_form'] = PaymentMethodForm(self.object.currency, initial={'order': self.object})
            return context


Here we get a ``PaymentMethodForm`` object, that is parametrised with the currency type. This is important, because this form will only display payment methods that accept the given currency.

``PaymentMethodForm`` provides two fields: HiddenInput with order_id and ChoiceField with the backend name. This is how you use it in a template::

    <form action="{% url 'getpaid:new-payment' currency=object.currency %}" method="post">
        {% csrf_token %}
        {{ payment_form.as_p }}
        <input type="submit" value="Continue">
    </form>


The action URL of this form should point to the named url  `getpaid:new-payment` that requires the currency code argument. This form will redirect the client from the order view directly to the page of the payment broker.


When client submits this form he will be redirected to getpaid internal view (``NewPaymentView``) which will do one of two things:

    * redirect client to a payment broker (directly, via HTTP 302) - this action is made if payment backend is
      configured to contact with payment broker via GET method,

      .. note::

        Using GET method is recommended as it involves less intermediate steps while creating a payment.

    * display intermediate page with a form with external action attribute - this action is made if
      payment backend is configured to use POST method (or this is the only way to communicate with payment
      broker).

      .. note::

        This intermediate page is displayed only to emulate making a POST request from the client side. getpaid
        displays a template ``"getpaid/payment_post_form.html"`` that should be definitely overridden in your
        project. On this page you should display some information *"please wait, you are being redirected to payment broker"* and add some JavaScript magic to submit the form automatically after page is loaded. The following context
        variables are available in this template:

            * ``form`` - a form with all input of type ``hidden``,
            * ``gateway_url`` - an external URL that should be used in ``action`` attribute of ``<form>``.

        This is an example of very basic template that could be used (assuming you are using jQuery)::

            <script>
                $(function(){
                    $("#new_payment").submit();
                });
            </script>
            <p> Please wait, you are being redirected to payment broker </p>
            <form action="{{ gateway_url }}" method="post" id="new_payment">
                {{ form.as_p }}
            </form>

      .. warning::
        Do **not** put the ``{% csrf %}`` token in this form, as it will result in a CSRF leak. CSRF tokens are only used for internal URLs. For more detailed
        info please read `Django CSRF Documentation <https://docs.djangoproject.com/en/dev/ref/contrib/csrf/#how-to-use-it>`_.

      .. warning::
        Remember that using POST methods do not bring any significant security over GET. On the one hand using POST is more correct according to the HTTP specification for actions that have side effects (like creating new payment), on the other hand using GET redirects is far easier in this particular case and it will not involve using hacks like "auto submitting forms on client side". That is the reason why using GET to connect with the payment broker system is recommended over using POST.

Filling necessary payment data
------------------------------

**Required**

Because the idea of whole module is that it should be loosely coupled, there is this convention that it does not require any structure of your order model. But it still needs to know some transaction details of your order. For that django signals are used. djang-getpaid while generating gateway redirect url will emit to your application a ``getpaid.signals.new_payment_query`` signal. Here is the signal declaration::

    new_payment_query = Signal(providing_args=['order', 'payment'])
    new_payment_query.__doc__ = """
    Sent to ask for filling Payment object with additional data:
        payment.amount:			total amount of an order
        payment.currency:		amount currency
    This data cannot be filled by ``getpaid`` because it is Order structure
    agnostic. After filling values just return. Saving is done outside signal.
    """

Your code has to implement some signal listeners that will inform the payment object with the required information::

    from getpaid import signals

    def new_payment_query_listener(sender, order=None, payment=None, **kwargs):
        """
        Here we fill only two obligatory fields of payment, and leave signal handler
        """
        payment.amount = order.total
        payment.currency = order.currency

    signals.new_payment_query.connect(new_payment_query_listener)


So this is a little piece of logic that you need to provide to map your order to a payment object. As you can see, you can do all fancy stuff here to get the order total value and currency code.

.. note::

    If you don't know where to put this code, put listener functions inside `signals.py` or `listeners.py` and
    `register them inside 'ready()' method of your app's config class <https://docs.djangoproject.com/en/1.11/ref/applications/#django.apps.AppConfig.ready>`_.

.. note::
    One may wonder why isn't this handled directly on the order model via methods like get_total() and get_currency(). It was a design consideration that you may not have access to your order model and therefore couldn't add these methods. By using signals, it does not matter if you have control or not over the order model.

**Optional**

Most likely you would also like to give some sort of information about your customer to your payment processor. The signal ``getpaid.signals.user_data_query`` fills this gap. Here is the declaration::

    user_data_query = Signal(providing_args=['order', 'user_data'])
    user_data_query.__doc__ = """
    Sent to ask for filling user additional data:
    	user_data['email']:		user email
    	user_data['lang']:      lang code in ISO 2-char format
    This data cannot be filled by ``getpaid`` because it is Order structure
    agnostic. After filling values just do return.
    """

On the example above we are passing the customer email and its desired language. Some backends may also need additional information like the customers address, phone, etc.

Handling changes of payment status
----------------------------------

**Required**

Signals are also used to inform you that some particular payment just changed status. In this case you will use ``getpaid.signals.payment_status_changed`` signal which is defined as::

    payment_status_changed = Signal(providing_args=['old_status', 'new_status'])
    payment_status_changed.__doc__ = """Sent when Payment status changes."""

example code that handles status changes::

    from getpaid import signals

    def payment_status_changed_listener(sender, instance, old_status, new_status, **kwargs):
        """
        Here we will actually do something, when payment is accepted.
        E.g. lets change an order status.
        """
        if old_status != 'paid' and new_status == 'paid':
            # Ensures that we process order only once
            instance.order.status = 'P'
            instance.order.save()

    signals.payment_status_changed.connect(payment_status_changed_listener)

For example, when the payment status changes to 'paid' status, this means that all necessary amount was verified by your payment broker. You have access to the order object at ``payment.order``.

Handling new payment creation
-----------------------------

**Optional**

For some reasons (e.g. for KPI benchmarking) it can be important to you to how many and which payments were made. For that reason you can handle ``getpaid.signals.new_payment`` signal defined as::

    new_payment = Signal(providing_args=['order', 'payment'])
    new_payment.__doc__ = """Sent after creating new payment."""


.. note::

    This method will enable you to make on-line KPI processing. For batch processing you can just query a database for Payment model as well.

Setup your payment backends
---------------------------

**Required**

Please be sure to read carefully section :doc:`backends` for information of how to configure particular backends. They will probably not work out of the box without providing some account keys or other credentials.
