"""Tests for django-getpaid system checks."""

import pytest

from getpaid.checks import (
    check_backend_settings,
    check_order_model,
)

pytestmark = pytest.mark.django_db


class TestOrderModelCheck:
    def test_valid_configuration_yields_no_errors(self):
        assert check_order_model(app_configs=None) == []

    def test_missing_setting_is_reported(self, settings):
        del settings.GETPAID_ORDER_MODEL

        errors = check_order_model(app_configs=None)

        assert len(errors) == 1
        assert errors[0].id == 'getpaid.E001'

    def test_unresolvable_model_is_reported(self, settings):
        settings.GETPAID_ORDER_MODEL = 'nonexistent.Model'

        errors = check_order_model(app_configs=None)

        assert len(errors) == 1
        assert errors[0].id == 'getpaid.E002'

    def test_malformed_value_is_reported(self, settings):
        settings.GETPAID_ORDER_MODEL = 'no-dots-here'

        errors = check_order_model(app_configs=None)

        assert len(errors) == 1
        assert errors[0].id == 'getpaid.E002'


class TestBackendSettingsCheck:
    def test_dict_is_accepted(self, settings):
        settings.GETPAID_BACKEND_SETTINGS = {'getpaid.backends.dummy': {}}

        assert check_backend_settings(app_configs=None) == []

    def test_absent_setting_is_accepted(self, settings):
        del settings.GETPAID_BACKEND_SETTINGS

        assert check_backend_settings(app_configs=None) == []

    def test_non_dict_is_reported(self, settings):
        settings.GETPAID_BACKEND_SETTINGS = ['not', 'a', 'dict']

        errors = check_backend_settings(app_configs=None)

        assert len(errors) == 1
        assert errors[0].id == 'getpaid.E003'

    def test_checks_are_registered(self):
        from django.core.checks.registry import registry

        registered = {
            getattr(check, '__name__', '') for check in registry.registered_checks
        }
        assert 'check_order_model' in registered
        assert 'check_backend_settings' in registered
