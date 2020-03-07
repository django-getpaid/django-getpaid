from abc import ABC, abstractmethod
from urllib.parse import urljoin, urlparse

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.urls import reverse


class BaseProcessor(ABC):
    production_url = None
    sandbox_url = None
    display_name = None
    accepted_currencies = None
    logo_url = None
    slug = None  # for friendly urls
    method = "GET"
    template_name = None

    def __init__(self, payment):
        self.payment = payment
        self.path = payment.backend
        self.context = {}  # can be used by Payment's customized methods.
        if self.slug is None:
            self.slug = self.path
        self.config = getattr(settings, "GETPAID_BACKEND_SETTINGS", {}).get(
            self.path, {}
        )

    @classmethod
    def class_id(cls):
        return cls.__module__

    def get_form(self, post_data):
        """
        Only used if the payment processor requires POST requests.
        Generates a form only containing hidden input fields.
        """
        from . import forms

        return forms.PaymentHiddenInputsPostForm(items=post_data)

    def handle_callback(self, request, *args, **kwargs):
        """
        This method handles the callback from payment broker for the purpose
        of updating the payment status in our system.
        :param args:
        :param kwargs:
        :return: HttpResponse instance
        """
        raise NotImplementedError

    @classmethod
    def get_display_name(cls) -> str:
        return cls.display_name

    @classmethod
    def get_accepted_currencies(cls) -> list:
        return cls.accepted_currencies

    @classmethod
    def get_logo_url(cls) -> str:
        return cls.logo_url

    def fetch_status(self) -> dict:
        """
        Logic for checking payment status with broker.

        Should return dict with either "amount" or "status" keys.
        If "status" key is used, it should be one of getpaid.models.PAYMENT_STATUS_CHOICES
        If both keys are present, "status" takes precedence.
        """
        raise NotImplementedError

    @abstractmethod
    def get_redirect_params(self, request=None) -> dict:
        """
        Gather all the data required by the broker.
        :return: dict
        """
        return {
            "success_url": request.build_absolute_uri(
                reverse("getpaid:payment-success", kwargs={"pk": self.payment.pk})
            ),
            "failure_url": request.build_absolute_uri(
                reverse("getpaid:payment-failure", kwargs={"pk": self.payment.pk})
            ),
        }

    def get_redirect_method(self) -> str:
        return self.method

    def get_redirect_url(self, params=None):
        """
        Provide URL to paywall. If method uses optional ``params`` argument,
        the resulting URL can be i.e. extracted from them (usually during REST
        flow) or constructed using them (usually during GET flow). Default
        implementation returns production or sandbox url based on DEBUG setting.
        """
        if settings.DEBUG:
            return self.sandbox_url
        return self.production_url

    def get_template_names(self, view=None) -> list:
        template_name = self.get_setting("POST_TEMPLATE")
        if template_name is None:
            template_name = getattr(settings, "GETPAID_POST_TEMPLATE", None)
        if template_name is None:
            template_name = self.template_name
        if template_name is None and hasattr(view, "get_template_names"):
            return view.get_template_names()
        if template_name is None:
            raise ImproperlyConfigured("Couldn't determine template name!")
        return [template_name]

    def get_setting(self, name, default=None):
        return self.config.get(name, default)

    def prepare_headers(self, obj: dict = None) -> dict:
        """
        Prepares HEADERS dict for REST or POST methods.
        """
        raise NotImplemented

    def handle_response(self, response) -> dict:
        """
        Analyze direct response from broker, update payment status if applicable,
        and return dict with extracted and normalized data.

        :param: response is expected to be ``request.response`` object.
        """
        raise NotImplemented
