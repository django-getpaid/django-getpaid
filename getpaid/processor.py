from abc import ABC, abstractmethod

from django.conf import settings


class BaseProcessor(ABC):
    production_url = None  #: Base URL of production environment.
    sandbox_url = None  #: Base URL of sandbox environment.
    display_name = None  #: The name of the provider for the ``choices``.
    accepted_currencies = None  #: List of accepted currency codes (ISO 4217).
    logo_url = None  #: Logo URL - can be used in templates.
    slug = None  #: For friendly urls
    ok_statuses = [
        200,
    ]  #: List of potentially successful HTTP status codes returned by paywall when creating payment

    def __init__(self, payment):
        self.payment = payment
        self.path = payment.backend
        self.context = {}  # can be used by Payment's customized methods.
        if self.slug is None:
            self.slug = self.path
        self.config = getattr(settings, "GETPAID_BACKEND_SETTINGS", {}).get(
            self.path, {}
        )
        self.optional_config = getattr(settings, "GETPAID", {})

    @classmethod
    def class_id(cls):
        return cls.__module__

    def get_setting(self, name, default=None):
        value = self.config.get(name, default)
        if value is None:
            value = self.optional_config.get(name, None)
        return value

    @classmethod
    def get_display_name(cls) -> str:
        return cls.display_name

    @classmethod
    def get_accepted_currencies(cls) -> list:
        return cls.accepted_currencies

    @classmethod
    def get_logo_url(cls) -> str:
        return cls.logo_url

    @classmethod
    def get_paywall_baseurl(cls):
        if settings.DEBUG:
            return cls.sandbox_url
        return cls.production_url

    @abstractmethod
    def process_payment(self, request, view) -> str:
        """
        Do what it takes to get the url redirecting user to paywall.

        :return: url to paywall for payment confirmation.
        """
        raise NotImplemented

    def handle_paywall_callback(self, request, *args, **kwargs):
        """
        This method handles the callback from paywall for the purpose
        of asynchronously updating the payment status in our system.

        :return: HttpResponse instance
        """
        raise NotImplementedError

    def fetch_payment_status(self) -> dict:
        # TODO use interface annotation to specify the dict layout
        """
        Logic for checking payment status with paywall.

        Should return dict with either "amount" or "status" keys.
        If "status" key is used, it should be one of getpaid.models.PAYMENT_STATUS_CHOICES
        If both keys are present, "status" takes precedence.
        """
        raise NotImplementedError

    def lock(self, amount=None):
        """
        Lock given amount for future charge.
        Returns amount locked amount.
        """
        raise NotImplemented

    def charge_locked(self, amount=None):
        """
        Check if payment can be locked and call processor's method.
        This method is used eg. in flows that pre-authorize payment during
        order placement and charge money upon shipping.
        Returns charged amount.
        """
        raise NotImplemented

    def release(self):
        """
        Release locked payment. This can happen if pre-authorized payment cannot
        be fullfilled (eg. the ordered product is no longer available for some reason).
        Returns released amount.
        """
        raise NotImplemented

    def refund(self, amount):
        """
        Refunds the given amount.

        Returns the amount that was actually refunded.
        """
        raise NotImplemented
