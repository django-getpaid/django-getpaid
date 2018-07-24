Payment backends
================

Payment backends are plug-and-play django applications that will make all necessary work to handle payment process via different money brokers. This way you can handle multiple payment providers (not only multiple payment methods!) what is wise taking into account possible problems like. breakdown or downtime of a single payment broker.

Each payment backend delivers a payment channel for a defined list of currencies. When using a ``PaymentMethodForm`` for displaying available payment methods for order it will automatically filter payment methods based on the provided payment currency. This is important as the system is designed to handle payments in multiple currencies. If you need to support currency conversions, you will need to do it before calling the payment method form in your part of application.

Just to have an overview, a payment backend has a very flexible architecture, allowing you to introduce your own logic, urls and even models.


.. warning::

    **Getting real client IP address from HTTP request meta**

    Many payment brokers for security reason require you to verify or provide real client IP address. For that reason the getpaid backend commonly uses ``REMOTE_ADDR`` HTTP meta. In most common production deployments your django app will stand after a number of proxy servers like Web server, caches, load balancers, you name it. This will cause that ``REMOTE_ADDR`` will almost **always** reflect the IP of your Web proxy server (e.g. 127.0.0.1 if everything is set up on local machine).

    For that reason you need to take care by yourself of having set ``REMOTE_ADDR`` correctly so that it actually points to **real** client IP. A good way to do that is to use commonly used HTTP header called ``X-Forwarded-For``. This header is set by most common Web proxy servers to the **real** client IP address. Using simple django middleware you can rewrite your request data to assure that **real** client IP address overwrites any address in ``REMOTE_ADDR``. One of the solutions taken from `The Django Book <http://www.djangobook.com/en/2.0/chapter17/>`_ is to use following middleware class::

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


    Enabling this middleware in your ``settings.py`` should fix the issue. Just make sure that your Web proxy server is actually setting ``X-Forwarded-For`` HTTP header.



.. warning::

    **Set Sites domain name**

    This module requires Sites framework to be enabled. All backends are based on Sites domain configuration (to generate a fully qualified URL for a payment broker service). Please be sure that you set a correct domain for your deployment before running ``getpaid`` or setup `GETPAID_SITE_DOMAIN` properly to point on the right domain (see `getpaid.utils.get_domain` for url fetching order).



Dummy backend ``getpaid.backends.dummy``
----------------------------------------
This is a mock of payment backend that can be used only for testing/demonstrating purposes.

Dummy backend is accepting only ``USD``, ``EUR`` or ``PLN`` currency transactions. After redirecting to a payment page it will display a dummy form where you can accept or decline a payment.

Enable backend
``````````````
Add backend full path to ``GETPAID_BACKENDS`` setting::

    GETPAID_BACKENDS += ('getpaid.backends.dummy', )


Don't forget to add backend path to ``INSTALLED_APPS`` as well::

    INSTALLED_APPS += ('getpaid.backends.dummy', )

Setup backend
`````````````
No additional setup is needed for the dummy backend.



New PayU.pl backend ``getpaid.backend.payu_rest``
-------------------------------------------------

The new REST-based PayU API. It can accept payments in several currencies.

Enable backend
``````````````
Add backend full path to ``GETPAID_BACKENDS`` setting::

    GETPAID_BACKENDS += ('getpaid.backends.payu_rest', )


Don't forget to add backend path to ``INSTALLED_APPS`` also::

    INSTALLED_APPS += ('getpaid.backends.payu_rest', )


Setup backend
`````````````

**pos_id**
    POS identificator,


**key2**
    according to PayU documentation this is a string that is used to compute md5 signature sent from Shop,

**client_id**
    client ID for OAuth handshake, usually equal to pos_id

**client_secret**
    secret required for OAuth handshake

**lang**
    default language for PayU pages

**ssl_return**
    boolean to indicate if the return url should be secure (defaults to True)


Legacy PayU.pl backend ``getpaid.backends.payu``
------------------------------------------------

This backend can handle payment processing via Polish money broker `PayU <http://payu.pl>`_ which is currently a part of the biggest e-commerce providers on Polish market - Allegro Group.

PayU accepts only payments in ``PLN``.

Enable backend
``````````````
Add backend full path to ``GETPAID_BACKENDS`` setting::

    GETPAID_BACKENDS += ('getpaid.backends.payu', )


Don't forget to add backend path to ``INSTALLED_APPS`` also::

    INSTALLED_APPS += ('getpaid.backends.payu', )


There is no need to add any url definitions to the main ``urls.py`` file, as they will be loaded automatically by ``getpaid`` application.

Setup backend
`````````````
In order to start working with PayU you will need to have an activated account in PayU service. There you will need to define a new Shop with new Point of Sale (POS). This will give you access to following configuration variables:


**pos_id**
    POS identificator,

**key1**
    according to PayU documentation this is a string that is used to compute md5 signature sent by Shop,

**key2**
    according to PayU documentation this is a string that is used to compute md5 signature sent from Shop,

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
    the HTTP method used to connect with broker system on new payment; default is 'GET';

**testing**
    when you test your service you can enable this option, all payments for PayU will have a predefined "Test Payment" method which is provided by PayU service (needs to be enabled); default is False;

`getpaid_configuration` management command
``````````````````````````````````````````
After setting up django application it is also important to remember that some minimal configuration is needed also at PayU service configuration site. Please navigate to POS configuration, where you need to provide three links: success URL, failure URL, and online URL. The first two are used to redirect client after successful/failure payment. The third one is the address of script that will be notified about payment status change.

``getpaid.backends.payu`` comes with ``getpaid_configuration`` management script that simplifies getting those links in your particular django environment. This is because you can customize path prefix when including urls from ``getpaid``.

It will produce the following example output::

    $. /manage.py  payu_configuration
    Login to PayU configuration page and setup following links:

     * Success URL: http://example.com/getpaid.backends.payu/success/%orderId%/
                    https://example.com/getpaid.backends.payu/success/%orderId%/

     * Failure URL: http://example.com/getpaid.backends.payu/failure/%orderId%/
                    https://example.com/getpaid.backends.payu/failure/%orderId%/

     * Online  URL: http://example.com/getpaid.backends.payu/online/
                    https://example.com/getpaid.backends.payu/online/

    To change the domain name please edit Sites settings. Don't forget to setup your web server to accept https connection in order to use secure links.

    Request signing is ON
     * Please be sure that you enabled signing payments in PayU configuration page.


.. warning::

    Please remember to set correct domain name in Sites framework.


Running celery for asynchronus tasks
````````````````````````````````````

This backend is asynchronous (as PayU requires an asynchronous architecture - they send a "ping" message that a payment change a status, and you need to asynchronously request theirs service for details of what has changed). That means that this backend requires django-celery application. Please refer to django-celery documentation for any additional information.

If you just want to make a quick start with using django-getpaid and django-celery please remember that after successful installation and enabling django-celery in your project you will need to run celery workers in order to process asynchronous task that this application requires. You can do that for example this way::

    $ python manage.py celery worker --loglevel=info






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
**PIN**
    secret used for checking messeges md5; generated in Dotpay admin panel


You need to provide this information in ``GETPAID_BACKENDS_SETTINGS`` dictionary::

    GETPAID_BACKENDS_SETTINGS = {
        'getpaid.backends.dotpay' : {
                'id' : 123456,
                'PIN': 123456789,

            },
    }

Optional keys:

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

**gateway_url**
    You may want to change this to use dotpay testing account; default: ``https://ssl.dotpay.eu/``

        .. warning::
Dotpay has strange policy regarding to gateway urls. It appears, that new accounts use ``https://ssl.dotpay.pl/``,
            but old accounts, that have 5-digit long id's, should still use old gateway ``https://ssl.dotpay.eu/``. For reasons
            of this behaviour You need to contact dotpay support.

