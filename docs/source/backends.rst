Payment backends
================

Payment backends are plug-and-play django applications that will make all necessary work to handle payment process via different money brokers. In this way you can handle multiple payment providers (not only multiple payment methods!) what is wise considering e.g. breakdown or downtime of a single payment broker.

Each payment backend delivers a payment channel for a defined list of currencies. When using ``PaymentMethodForm`` for displaying available payment methods for order it will automatically filter payment methods based on the provided payment currency. This is important as the system is designed to handle payments in multiple currencies. If you need to support currency conversions, you will need to do it before calling the payment method form in your part of application.

Just to have an overview, a payment backend has a very flexible architecture, allowing you to introduce your own logic, urls and even models.


.. warning::

    **Getting real client IP address from HTTP request meta**

    Many payment brokers for security reason requires checking or providing real clint IP address. For that reason the getpaid backend commonly uses ``REMOTE_ADDR`` HTTP meta. In most common production deployments your django app will stand after a number of proxy servers like Web server, caches, load balancers, you name it. This will cause that ``REMOTE_ADDR`` will **always** be set for your application as an IP of your Web proxy server (e.g. 127.0.0.0 if everything is set up on local machine).

    For that reason you need to take care by yourself of having correctly set ``REMOTE_ADDR`` that actually points on **real** client IP. A good way to do that is to use commonly used HTTP header called ``X-Forwarded-For``. This is a header that is set by most common Web proxy servers  to the **real** client IP address. Using simple django middleware you can rewrite your request data to assure that **real** client IP address overwrites any address  in ``REMOTE_ADDR``. One of solution taken from `The Django Book <http://www.djangobook.com/en/2.0/chapter17/>`_ is to use following middleware class::

        class SetRemoteAddrFromForwardedFor(object):
            def process_request(self, request):
                try:
                    real_ip = request.META['HTTP_X_FORWARDED_FOR']
                except KeyError:
                    pass
                else:
                    # HTTP_X_FORWARDED_FOR can be a comma-separated list of IPs.
                    # Take just the first one.
                    real_ip = real_ip.split(",")[0]
                    request.META['REMOTE_ADDR'] = real_ip


    Enabling this middleware in your ``settings.py`` will fix the issue. Just make sure that your Web proxy server is actually setting ``X-Forwarded-For`` HTTP header.



.. warning::

    **Set Sites domain name**

    This module requires Sites framework to be enabled. All backends base on Sites domain configuration (to generate fully qualified URL for payment broker service). Please be sure that you set a correct domain for your deployment before running ``getpaid``.



Dummy backend ``getpaid.backends.dummy``
----------------------------------------
This is a mock of payment backend that can be used only for testing/demonstrating purposes.

Dummy backend is accepting only ``USD``, ``EUR`` or ``PLN`` currency transactions. After redirecting to payment page it will display a dummy form where you can accept or decline a payment.

Enable backend
``````````````
Add backend full path to ``GETPAID_BACKENDS`` setting::

    GETPAID_BACKENDS += ('getpaid.backends.dummy', )


Don't forget to add backend path also to ``INSTALLED_APPS``::

    INSTALLED_APPS += ('getpaid.backends.dummy', )

Setup backend
`````````````
No additional setup is needed for dummy backend.




PayU.pl backend ``getpaid.backends.payu``
-----------------------------------------
This backend can handle payment processing via Polish money broker `PayU <http://payu.pl>`_ which is currently a part of the biggest on Polish market e-commerce provider - Allegro Group.

PayU accepts only payments in ``PLN``.

Enable backend
``````````````
Add backend full path to ``GETPAID_BACKENDS`` setting::

    GETPAID_BACKENDS += ('getpaid.backends.payu', )


Don't forget to add backend path also to ``INSTALLED_APPS``::

    INSTALLED_APPS += ('getpaid.backends.payu', )


There is no need to adding any urls definitions to main ``urls.py`` file, as they will be loaded automatically itself by ``getpaid`` application.

Setup backend
`````````````
In order to start working with PayU you will need to have an activated account in PayU service. In this service you will need to define a new Shop with new Point of Sale (POS). After that you will have an access to following configuration variables.


**pos_id**
    identificator of POS,

**key1**
    according to PayU documentation this is a string that is used to compute md5 signature send by Shop,

**key2**
    according to PayU documentation this is a string that is used to compute md5 signature send from Shop,

**pos_auth_key**
    just a kind of secret password for POS.


You need to provide this information in ``GETPAID_BACKENDS_SETTINGS`` dictionary::

    GETPAID_BACKENDS_SETTINGS = {
        'getpaid.backends.payu' : {
                'pos_id' : 123456,
                'key1' : 'xxxxxxxxxxxxx',
                'key2' : 'xxxxxxxxxxxxx',
                'pos_auth_key': 'xxxxxxxxx',
                'signing' : True,       # optional
                'testing' : True,       # optional
            },
    }

There are some additional options you can provide:

**lang**
    default interface lang (refer to PayU manual); default: ``None``

**signing**
    for security reasons PayU can check a signature of all data that is sent from your service while redirecting to payment gateway; unless you really know what you are doing, this should be always on; default is True;

**method**
    the HTTP method how to connect with broker system on new payment; default is 'GET';

**testing**
    when you test your service you can enable this option, all payments for PayU will have predefined "Test Payment" method which is provided by PayU service (need to be enabled); default is False;

`getpaid_configuration` management command
``````````````````````````````````````````
After setting up django application it is also important to remember that some minimal configuration is needed also at PayU service configuration site. Please navigate to POS configuration, where you need to provide three links: success URL, failure URL, and online URL. The first two are used to redirect client after successful/failure payment. The third one is the address of script that will be notified about payment status change.

``getpaid.backends.payu`` comes with ``getpaid_configuration`` management script that simplifies getting those links in your particular django environment. This is because you can customize path prefix when including urls from ``getpaid``.

It will produce following example output::

    $. /manage.py  payu_configuration
    Login to PayU configuration page and setup following links:

     * Success URL: http://example.com/getpaid.backends.payu/success/%orderId%/
                    https://example.com/getpaid.backends.payu/success/%orderId%/

     * Failure URL: http://example.com/getpaid.backends.payu/failure/%orderId%/
                    https://example.com/getpaid.backends.payu/failure/%orderId%/

     * Online  URL: http://example.com/getpaid.backends.payu/online/
                    https://example.com/getpaid.backends.payu/online/

    To change domain name please edit Sites settings. Don't forget to setup your web server to accept https connection in order to use secure links.

    Request signing is ON
     * Please be sure that you enabled signing payments in PayU configuration page.


.. warning::

    Please remember to set correct domain name in Sites framework.


Running celery for asynchronus tasks
````````````````````````````````````

This backend is asynchronous (as PayU requires an asynchronous architecture - they send a "ping" message that a payment change a status, and you need to asynchronously request theirs service for details of what has changed). That means that this backend requires django-celery application. Please refer to django-celery documentation for any additional information.

If you just want to make a quick start with using django-getpaid and django-celery please remember that after successful installation and enabling django-celery in your project you will need to run celery workers in order to process asynchronous task that this application requires. You do that for example in this way::

    $ python manage.py celery worker --loglevel=info





Transferuj.pl backend ``getpaid.backends.transferuj``
-----------------------------------------------------

This backend can handle payment processing via Polish money broker `Transferuj.pl <http://transferuj.pl>`_.

Transferuj.pl accepts only payments in ``PLN``.



Enable backend
``````````````
Add backend full path to ``GETPAID_BACKENDS`` setting::

    GETPAID_BACKENDS += ('getpaid.backends.transferuj', )


Don't forget to add backend path also to ``INSTALLED_APPS``::

    INSTALLED_APPS += ('getpaid.backends.transferuj', )


There is no need to adding any urls definitions to main ``urls.py`` file, as they will be loaded automatically itself by ``getpaid`` application.

Setup backend
`````````````
In order to start working with Transferuj.pl you will need to have an activated account in Transferuj.pl service. The following setup information need to be provided in the ``GETPAID_BACKENDS_SETTINGS`` configuration dict:


**id**
    Transferuj.pl client identificator,

**key**
    random (max. 16 characters long) string, that will be used in security signing of requests,


You need to provide this information in ``GETPAID_BACKENDS_SETTINGS`` dictionary::

    GETPAID_BACKENDS_SETTINGS = {
        'getpaid.backends.transferuj' : {
                'id' : 123456,
                'key' : 'xxxxxxxxxxxxx',
                'signing' : True,       # optional
            },
    }

There are some additional options you can provide:

**signing**
    for security reasons Transferuj.pl can check a signature of some data that is sent from your service while redirecting to payment gateway; unless you really know what you are doing, this should be always on; default is True;

**method**
    the HTTP method how to connect with broker system on new payment; default is 'GET';

**allowed_ip**
    Transferuj.pl requires to check IP address when they send you a payment status change HTTP request. By default,
    this module comes with list of hardcoded IP of Transferuj.pl system (according to the documentation). If you
    really need to you can override this list of allowed IP, setting this variable.

    .. note::

        Setting empty list ``[]`` completely disables checking of IP address what **NOT recommended**.

**force_ssl_online**
    default: False; this option when turned to True, will force getpaid to return an HTTPS URL for Transferuj.pl to send
    you payment status change.

    .. warning::

        Remember to set Sites framework domain in database, as this module uses this address to build fully qualified
        URL.

**force_ssl_return**
    default: False; similarly to ``force_ssl_online`` but forces HTTPS for client returning links.

    .. warning::

        Remember to set Sites framework domain in database, as this module uses this address to build fully qualified
        URL.

`transferuj_configuration` management command
`````````````````````````````````````````````
After setting up django application it is also important to remember that some minimal configuration is needed also at Transferuj.pl service configuration site.

``getpaid.backends.transferuj`` comes with ``transferuj_configuration`` management script that simplifies getting those links in your particular django eviroment. This is because you can customize path prefix when including urls from ``getpaid``.

It will produce following example output::

    $. /manage.py  transferuj_configuration
    Please setup in Transferuj.pl user defined key (for security signing): xxxxxxxxxxxxx


.. warning::

    Please remember to set correct domain name in Sites framework.



Dotpay.eu backend ``getpaid.backends.dotpay``
---------------------------------------------

This backend can handle payment processing via Polish money broker `Dotpay.pl/Dotpay.eu <http://dotpay.eu>`_.

Dotpay.eu accepts payments in ``PLN``, ``EUR``, ``USD``, ``GBP``, ``JPY``, ``CZK``, ``SEK``.


Setup backend
`````````````
In order to start working with Dotpay you will need to have an activated account in Dotpay service.

Required keys:

**id**
    client ID


You need to provide this information in ``GETPAID_BACKENDS_SETTINGS`` dictionary::

    GETPAID_BACKENDS_SETTINGS = {
        'getpaid.backends.dotpay' : {
                'id' : 123456,

            },
    }

Optional keys:

**PIN**
    secret used for checking messeges md5; default ``""``

**force_ssl**
    forcing HTTPS on incoming connections from Dotpay; default ``False``

    .. warning::

        **Set Sites domain name**

        This module requires Sites framework to be enabled. All backends base on Sites domain configuration (to generate fully qualified URL for payment broker service). Please be sure that you set a correct domain for your deployment before running ``getpaid``.

**method**
    the HTTP method how to connect with broker system on new payment; default is 'GET';

**lang**
    default interface lang (refer to Dotpay manual); default: ``None``

**onlinetransfer**
    if broker should show only online payment methods (refer to Dotpay manual); default: ``False``

**p_email**
    custom merchant e-mail (refer to Dotpay manual); default: ``None``

**p_info**
    custom merchant name (refer to Dotpay manual); default: ``None``

**tax**
    1% charity (refer to Dotpay manual); default: ``False``
    
    
    
    
    
PagSeguro backend ``getpaid.backends.pagseguro``
---------------------------------------------

This backend can handle payment processing via brazilian money broker `PagSeguro.com.br <http://pagseguro.com.br>`_.

PagSeguro accepts payments exclusively in ``BRL``.


Setup backend
`````````````
In order to start working with PagSeguro you will need to have an activated account with PagSeguro.

Required keys:

**email**
    your seller's account e-mail
    
**token**
    your secret token


You need to provide this information in ``GETPAID_BACKENDS_SETTINGS`` dictionary::

    GETPAID_BACKENDS_SETTINGS = {
        'getpaid.backends.pagseguro' : {
                'email': 'test@test.com',
                'token': "AB310XDOPQO13LXPAO"
            },
    }
    
    
Status changes
`````````````
Even though PagSeguro has 7 different statuses (pending, verifying, paid, available, in dispute, refunded and canceled), this only translates into 3 statuses in `django-getpaid`. Before the payment is made, the initial status is `in_progress`. Once it moves in PagSeguro to the paid state, this state also changes on this backend to paid. If at any point PagSeguro changes the transaction status to canceled or refunded, the status on this backend will also enter the failed state. Beware that all others statuses in between are ignored. You will not be notified if a transaction moves from paid to available or if it enters dispute. This should however make no difference, as it only really matters if your transaction at PagSeguro changes from in dispute to refunded or cancelled (and both are tracked).
