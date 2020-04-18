from abc import ABC, abstractmethod
from importlib import import_module

from django.conf import settings
from django.contrib.sites.shortcuts import get_current_site
from django.core.exceptions import ImproperlyConfigured


class BaseProcessor(ABC):
    production_url = None  #: Base URL of production environment.
    sandbox_url = None  #: Base URL of sandbox environment.
    display_name = None  #: The name of the provider for the ``choices``.
    accepted_currencies = None  #: List of accepted currency codes (ISO 4217).
    logo_url = None  #: Logo URL - can be used in templates.
    slug = None  #: For friendly urls
    post_form_class = None
    post_template_name = None
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
    def class_id(cls, **kwargs):
        return cls.__module__

    def get_setting(self, name, default=None):
        value = self.config.get(name, default)
        if value is None:
            value = self.optional_config.get(name, None)
        return value

    @classmethod
    def get_display_name(cls, **kwargs) -> str:
        return cls.display_name

    @classmethod
    def get_accepted_currencies(cls, **kwargs) -> list:
        return cls.accepted_currencies

    @classmethod
    def get_logo_url(cls, **kwargs) -> str:
        return cls.logo_url

    @classmethod
    def get_paywall_baseurl(cls, **kwargs):
        if settings.DEBUG:
            return cls.sandbox_url
        return cls.production_url

    @staticmethod
    def get_our_baseurl(request=None, **kwargs):
        """
        Little helper function to get base url for our site.
        Note that this way 'https' is enforced on production environment.
        """
        scheme = "http" if settings.DEBUG else "https"
        return f"{scheme}://{get_current_site(request).domain}/"

    def get_template_names(self, view=None, **kwargs) -> list:
        template_name = self.get_setting("POST_TEMPLATE")
        if template_name is None:
            template_name = self.post_template_name
        if template_name is None and hasattr(view, "get_template_names"):
            return view.get_template_names()
        if template_name is None:
            raise ImproperlyConfigured("Couldn't determine template name!")
        return [template_name]

    def get_form_class(self, **kwargs):
        form_class_path = self.get_setting("POST_FORM_CLASS")
        if not form_class_path:
            return self.post_form_class
        if isinstance(form_class_path, str):
            module_path, class_name = form_class_path.rsplit(".", 1)
            module = import_module(module_path)
            return getattr(module, class_name)
        return self.post_form_class

    def prepare_form_data(self, post_data, **kwargs):
        """
        If backend support several modes of operation, POST should probably
        additionally calculate some sort of signature based on passed data.
        """
        return post_data

    def get_form(self, post_data, **kwargs):
        """
        (Optional)
        Used to get POST form for backends that use such flow.
        """
        form_class = self.get_form_class()
        if form_class is None:
            raise ImproperlyConfigured("Couldn't determine form class!")

        form_data = self.prepare_form_data(post_data)

        return form_class(fields=form_data)

    # Communication with outer world

    @abstractmethod
    def prepare_transaction(self, request, view=None, **kwargs):
        """
        Prepare Response for the view asking to prepare transaction.

        :return: HttpResponse instance
        """
        raise NotImplementedError

    def handle_paywall_callback(self, request, **kwargs):
        """
        This method handles the callback from paywall for the purpose
        of asynchronously updating the payment status in our system.

        :return: HttpResponse instance that will be presented as answer to the callback.
        """
        raise NotImplementedError

    def fetch_payment_status(self, **kwargs) -> dict:
        # TODO use interface annotation to specify the dict layout
        """
        Logic for checking payment status with paywall.

        Should return dict with either "amount" or "status" keys.
        If "status" key is used, it should be one of getpaid.models.PAYMENT_STATUS_CHOICES
        If both keys are present, "status" takes precedence.
        """
        raise NotImplementedError

    def charge(self, amount=None, **kwargs):
        """
        (Optional)
        Check if payment can be locked and call processor's method.
        This method is used eg. in flows that pre-authorize payment during
        order placement and charge money later.
        Returns charged amount.
        """
        raise NotImplementedError

    def release_lock(self, **kwargs):
        """
        (Optional)
        Release locked payment. This can happen if pre-authorized payment cannot
        be fullfilled (eg. the ordered product is no longer available for some reason).
        Returns released amount.
        """
        raise NotImplementedError

    def start_refund(self, amount=None, **kwargs):
        """
        Refunds the given amount.

        Returns the amount that was actually refunded.
        """
        raise NotImplementedError

    def cancel_refund(self, **kwargs):
        """
        Cancels started refund.

        Returns True/False if the cancel succeeded.
        """
        raise NotImplementedError
