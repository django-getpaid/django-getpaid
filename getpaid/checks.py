"""Django system checks for django-getpaid configuration."""

from django.apps import apps as django_apps
from django.conf import settings as django_settings
from django.core import checks


@checks.register(checks.Tags.models)
def check_order_model(app_configs, **kwargs):
    """Validate that GETPAID_ORDER_MODEL is set and resolvable."""
    label = getattr(django_settings, 'GETPAID_ORDER_MODEL', None)
    if not label:
        return [
            checks.Error(
                'GETPAID_ORDER_MODEL setting is not set.',
                hint=(
                    "Point it at your order model, e.g. "
                    "GETPAID_ORDER_MODEL = 'yourapp.Order'."
                ),
                id='getpaid.E001',
            )
        ]
    try:
        django_apps.get_model(label)
    except (ValueError, LookupError):
        return [
            checks.Error(
                f'GETPAID_ORDER_MODEL refers to model {label!r} '
                'that cannot be resolved.',
                hint=(
                    "Use the 'app_label.ModelName' form and make sure "
                    'the app is in INSTALLED_APPS.'
                ),
                id='getpaid.E002',
            )
        ]
    return []


@checks.register(checks.Tags.compatibility)
def check_backend_settings(app_configs, **kwargs):
    """Validate that GETPAID_BACKEND_SETTINGS is a dict when present."""
    backend_settings = getattr(
        django_settings, 'GETPAID_BACKEND_SETTINGS', None
    )
    if backend_settings is None:
        return []
    if not isinstance(backend_settings, dict):
        return [
            checks.Error(
                'GETPAID_BACKEND_SETTINGS must be a dict mapping backend '
                'paths to their configuration, got '
                f'{type(backend_settings).__name__}.',
                id='getpaid.E003',
            )
        ]
    return []
