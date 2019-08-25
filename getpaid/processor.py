from abc import ABC, abstractmethod

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


class BaseProcessor(ABC):
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
            self.slug = payment.backend  # no more Mr. Friendly :P
        self.config = getattr(settings, "GETPAID_BACKEND_SETTINGS", {}).get(
            self.path, {}
        )

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
    def get_display_name(cls):
        return cls.display_name

    @classmethod
    def get_accepted_currencies(cls):
        return cls.accepted_currencies

    @classmethod
    def get_logo_url(cls):
        return cls.logo_url

    def fetch_status(self):
        """
        Logic for checking payment status with broker.

        Should return dict with either "amount" or "status" keys.
        If "status" key is used, it should be one of getpaid.models.PAYMENT_STATUS_CHOICES
        If both keys are present, "status" takes precedence.
        """
        raise NotImplementedError

    @abstractmethod
    def get_redirect_params(self):
        return {}

    def get_redirect_method(self):
        return self.method

    @abstractmethod
    def get_redirect_url(self):
        return

    def get_template_names(self, view=None):
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
