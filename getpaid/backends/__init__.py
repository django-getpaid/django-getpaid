from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.template.base import Template
from django.template.context import Context
import six
from getpaid.utils import get_backend_settings


class PaymentProcessorBase(object):
    """
    Base for all payment processors. It should at least be able to:
     * redirect to a gateway based on Payment object
     * manage all necessary logic to accept payment from gateway, e.g. expose
       a View for incoming transaction notification status changes
    """

    # Each backend needs to define these values
    BACKEND = None
    """
    This constant should be set to fully qualified python path to the module. This is also
    a name that will be used to identify and enabling this backend in django-getpaid
    """
    BACKEND_NAME = None
    """
    This constant should be set to human readable backend name. Consider using lazy translation strings
    for i18n support
    """
    BACKEND_ACCEPTED_CURRENCY = tuple()
    """
    This constant should be any type of iterable that defines accepted currencies by the backend. Currencies should be
    set as three letters ISO code strings (eg. 'USD', 'EUR')
    """
    BACKEND_LOGO_URL = None
    """
    A path in static root where payment logo could be find.
    """

    def __init__(self, payment, test_mode=False):

        if payment.currency not in self.BACKEND_ACCEPTED_CURRENCY:
            raise ValueError("Backend '%s' cannot process '%s' payments." % (self.BACKEND, payment.currency))
        self.payment = payment
        self.test_mode = test_mode

    @classmethod
    def get_logo_url(cls):
        """
        Get backend logo. Use always this method, instead of reading BACKEND_LOGO_URL attribute directly.

        :return: str
        """
        return cls.BACKEND_LOGO_URL

    def get_order_description(self, payment, order):
        """
        Renders order description using django template provided in ``settings.GETPAID_ORDER_DESCRIPTION``
        or if not provided return unicode representation of ``Order object``.
        """
        template = getattr(settings, 'GETPAID_ORDER_DESCRIPTION', None)
        if template:
            return Template(template).render(Context({"payment": payment, "order": order}))
        else:
            return six.text_type(order)

    def get_gateway_url(self, request):
        """
        Should return a tuple with the first item being the URL that redirects to payment Gateway
        Second item should be if the request is made via GET or POST. Third item are the parameters
        to be passed in case of a POST REQUEST. Request context need to be given because various
        payment engines requires information about client (e.g. a client IP).
        """
        raise NotImplementedError('Must be implemented in PaymentProcessor')

    def get_form(self, post_data):
        """
        Only used if the payment processor requires POST requests.
        Generates a form only containg hidden input fields.
        """
        from getpaid.forms import PaymentHiddenInputsPostForm
        return PaymentHiddenInputsPostForm(items=post_data)

    @classmethod
    def get_backend_setting(cls, name, default=None):
        """
        Reads ``name`` setting from backend settings dictionary.

        If `default` value is omitted, raises ``ImproperlyConfigured`` when
        setting ``name`` is not available.
        """
        backend_settings = get_backend_settings(cls.BACKEND)
        if default is not None:
            return backend_settings.get(name, default)
        else:
            try:
                return backend_settings[name]
            except KeyError:
                raise ImproperlyConfigured("getpaid '%s' requires backend '%s' setting" % (cls.BACKEND, name))
