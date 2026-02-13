"""Django-specific payment processor base class.

Extends getpaid-core's BaseProcessor with Django settings integration,
template handling, and URL helpers.
"""

from collections.abc import Mapping
from importlib import import_module
from typing import Any

from django.conf import settings
from django.contrib.sites.shortcuts import get_current_site
from django.core.exceptions import ImproperlyConfigured
from django.forms import BaseForm
from django.http import HttpRequest
from django.views import View
from getpaid_core.processor import BaseProcessor as CoreBaseProcessor


class BaseProcessor(CoreBaseProcessor):
    """Django adapter for core BaseProcessor.

    Adds Django settings integration, template handling,
    and URL helpers on top of core's abstract methods.
    """

    production_url: str | None = None
    sandbox_url: str | None = None
    post_form_class: type | None = None
    post_template_name: str | None = None
    client_class: type | str | None = None
    client: object | None = None
    ok_statuses: list[int] = [200]

    def __init__(self, payment, config=None) -> None:
        # Read config from Django settings if not provided
        if config is None:
            path = getattr(payment, 'backend', '') or ''
            config = getattr(settings, 'GETPAID_BACKEND_SETTINGS', {}).get(
                path, {}
            )
        super().__init__(payment, config=config)
        self.path = getattr(payment, 'backend', '') or ''
        self.context: dict = {}
        if self.slug is None:
            self.slug = self.path  # ty: ignore[invalid-attribute-access]
        self.optional_config = getattr(settings, 'GETPAID', {})
        if self.client_class is not None:
            self.client = self.get_client()

    def get_setting(self, name: str, default: Any | None = None) -> Any:
        """Read setting from backend config, falling back to GETPAID global."""
        value = self.config.get(name, default)
        if value is None:
            value = self.optional_config.get(name, None)
        return value

    def get_client_class(self) -> type | None:
        class_path = self.get_setting('CLIENT_CLASS')
        if not class_path:
            class_path = self.client_class
        if class_path and not callable(class_path):
            module_name, _, class_name = class_path.rpartition('.')
            module = import_module(module_name)
            return getattr(module, class_name)
        return class_path  # ty: ignore[invalid-return-type]

    def get_client(self) -> object:
        client_class = self.get_client_class()
        if client_class is None:
            raise ImproperlyConfigured('No client class configured!')
        return client_class(**self.get_client_params())

    def get_client_params(self) -> dict:
        return {}

    @classmethod
    def class_id(cls, **kwargs) -> str:
        return cls.__module__

    @classmethod
    def get_display_name(cls, **kwargs) -> str:
        return cls.display_name

    @classmethod
    def get_accepted_currencies(cls, **kwargs) -> list[str]:
        return cls.accepted_currencies

    @classmethod
    def get_logo_url(cls, **kwargs) -> str | None:
        return cls.logo_url

    @classmethod
    def get_paywall_baseurl(cls, **kwargs) -> str | None:  # ty: ignore[invalid-method-override]
        if settings.DEBUG:
            return cls.sandbox_url
        return cls.production_url

    @staticmethod
    def get_our_baseurl(request: HttpRequest | None = None, **kwargs) -> str:
        """Get base URL for our site.

        Uses Sites framework when no request is available.
        """
        scheme = 'http' if settings.DEBUG else 'https'
        if request is not None:
            domain = get_current_site(request).domain
        else:
            # Circular import workaround: Site model loaded at runtime
            from django.contrib.sites.models import Site

            domain = Site.objects.get_current().domain
        return f'{scheme}://{domain}/'

    def get_template_names(
        self, view: View | None = None, **kwargs
    ) -> list[str]:
        template_name = self.get_setting('POST_TEMPLATE')
        if template_name is None:
            template_name = self.post_template_name
        if (
            template_name is None
            and view is not None
            and hasattr(view, 'get_template_names')
        ):
            return view.get_template_names()  # ty: ignore[call-non-callable]
        if template_name is None:
            raise ImproperlyConfigured("Couldn't determine template name!")
        return [template_name]

    def get_form_class(self, **kwargs) -> type | None:
        form_class_path = self.get_setting('POST_FORM_CLASS')
        if not form_class_path:
            return self.post_form_class
        if isinstance(form_class_path, str):
            module_path, class_name = form_class_path.rsplit('.', 1)
            module = import_module(module_path)
            return getattr(module, class_name)
        return self.post_form_class

    def prepare_form_data(self, post_data: dict, **kwargs) -> Mapping[str, Any]:
        return post_data

    def get_form(self, post_data: dict, **kwargs) -> BaseForm:
        form_class = self.get_form_class()
        if form_class is None:
            raise ImproperlyConfigured("Couldn't determine form class!")
        form_data = self.prepare_form_data(post_data)
        return form_class(fields=form_data)

    def verify_callback(  # ty: ignore[invalid-method-override]
        self, request: HttpRequest, **kwargs
    ) -> None:
        """Verify callback from Django request. Override in backends.

        Default: no-op (accepts all callbacks).
        The signature intentionally differs from the core's async version —
        Django adapter wraps the HTTP request differently.
        """

    def handle_paywall_callback(self, request, **kwargs):
        """Handle paywall callback. Override in backends."""
        raise NotImplementedError

    def fetch_payment_status(self, **kwargs):
        """Fetch payment status from gateway. Override in backends."""
        raise NotImplementedError
