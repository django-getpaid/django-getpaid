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
    BACKEND_NAME = None
    BACKEND_ACCEPTED_CURRENCY = None

    def __init__(self, payment):

        if payment.currency not in self.BACKEND_ACCEPTED_CURRENCY:
            raise ValueError("Backend '%s' cannot process '%s' payments." % self.BACKEND, payment.currency)
        self.payment = payment


    def get_gateway_url(self, request):
        """
        Returns an URL that redirects to payment Gateway. Request context need to be given
        because various payment engines requires information about client (like IP).
        """
        raise NotImplementedError('Must be implemented in PaymentProcessor')

    @classmethod
    def get_backend_setting(cls, name, default=None):
        """
        Reads setting from backend settings dictionary.

        If ``default`` value is omitted, raises ``ImproperlyConfigured` when
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