from abc import ABC, abstractmethod

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.urls import reverse


class BaseProcessor(ABC):
    production_url = None  #: Base URL of production environment.
    sandbox_url = None  #: Base URL of sandbox environment.
    display_name = None  #: The name of the provider for the ``choices``.
    accepted_currencies = None  #: List of accepted currency codes (ISO 4217).
    logo_url = None  #: Logo URL - can be used in templates.
    slug = None  #: For friendly urls
    method = "GET"  #: Method of operation. One of GET, POST or REST.
    template_name = None  #: Template used in the POST method flow.

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
        return self.config.get(name, default)

    @classmethod
    def get_display_name(cls) -> str:
        return cls.display_name

    @classmethod
    def get_accepted_currencies(cls) -> list:
        return cls.accepted_currencies

    @classmethod
    def get_logo_url(cls) -> str:
        return cls.logo_url

    def get_paywall_method(self) -> str:
        return self.method

    def get_form(self, post_data):
        """
        Only used if the payment processor requires POST requests.
        Generates a form only containing hidden input fields.
        """
        from . import forms

        return forms.PaymentHiddenInputsPostForm(items=post_data)

    def get_paywall_baseurl(self):
        if settings.DEBUG:
            return self.sandbox_url
        return self.production_url

    def get_paywall_url(self, params=None):
        """
        Provide URL to paywall. If method uses optional ``params`` argument,
        the resulting URL can be i.e. extracted from them (usually during REST
        flow) or constructed using them (usually during GET flow). Default
        implementation returns production or sandbox url based on DEBUG setting.
        """
        return self.get_paywall_baseurl()

    def get_template_names(self, view=None) -> list:
        template_name = self.get_setting("POST_TEMPLATE")
        if template_name is None:
            template_name = self.optional_config.get("POST_TEMPLATE")
        if template_name is None:
            template_name = self.template_name
        if template_name is None and hasattr(view, "get_template_names"):
            return view.get_template_names()
        if template_name is None:
            raise ImproperlyConfigured("Couldn't determine template name!")
        return [template_name]

    @abstractmethod
    def get_paywall_params(self, request) -> dict:
        """
        Gather all the data required by the broker.

        :param request:
        :return: Dict of all params accepted by paywall API.
        """
        raise NotImplemented

    def prepare_paywall_headers(self, obj: dict = None) -> dict:
        """
        Prepares HEADERS dict for REST or POST methods. This is where you will
        probably calculate the signature of ``obj``.

        :param dict obj: Serialized payment object that you can use to calculate signature.
        :return: Dictionary of headers that must be attached to a request to paywall.
        """
        raise NotImplemented

    def handle_paywall_response(self, response) -> dict:
        """
        Analyze direct response from broker, update payment status if applicable,
        and return dict with extracted and normalized data.

        :param response: is expected to be :py:mod:`request.response` object.
        """
        raise NotImplemented

    def handle_paywall_callback(self, request, *args, **kwargs):
        """
        This method handles the callback from payment broker for the purpose
        of asynchronously updating the payment status in our system.

        :return: HttpResponse instance
        """
        raise NotImplementedError

    def fetch_payment_status(
        self,
    ) -> dict:  # TODO use interface annotation to specify the dict layout
        """
        Logic for checking payment status with broker.

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
