from django.core.exceptions import ImproperlyConfigured
from getpaid.utils import get_backend_settings

class PaymentProcessorBase(object):
    """
    Base for all payment processors. It should at least be able to:
     * redirect to a gateway based on Payment object
     * manage all necessary logic to accept payment from gateway, e.g. expose
       a View for incoming transaction notification status changes
    """

    #Each backend need to define this values
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

    def __init__(self, payment):

        if payment.currency not in self.BACKEND_ACCEPTED_CURRENCY:
            raise ValueError("Backend '%s' cannot process '%s' payments." % self.BACKEND, payment.currency)
        self.payment = payment


    def get_gateway_url(self, request):
        """
        Should return an URL that redirects to payment Gateway. Request context need to be given
        because various payment engines requires information about client (e.g. a client IP).
        """
        raise NotImplementedError('Must be implemented in PaymentProcessor')

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