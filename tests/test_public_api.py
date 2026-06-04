"""Tests for the public package API."""

import tomllib
from pathlib import Path

import getpaid_core
import getpaid_paynow

import getpaid


def test_version() -> None:
    assert getpaid.__version__ == '3.0.0'


def test_core_dependency_floor() -> None:
    current_version = getpaid.__version__
    pyproject_data = tomllib.loads(Path('pyproject.toml').read_text())
    assert (
        f'python-getpaid-core>={current_version}'
        in pyproject_data['project']['dependencies']
    )
    assert (
        f'python-getpaid-core>={current_version}'
        in pyproject_data['dependency-groups']['dev']
    )


def test_paynow_dev_dependency_floor() -> None:
    current_version = getpaid.__version__
    pyproject_data = tomllib.loads(Path('pyproject.toml').read_text())

    assert (
        f'python-getpaid-paynow>={current_version}'
        in pyproject_data['dependency-groups']['dev']
    )


def test_ecosystem_versions_match() -> None:
    assert getpaid.__version__ == getpaid_core.__version__
    assert getpaid.__version__ == getpaid_paynow.__version__


class TestExpandedPublicAPI:
    """Tests that django-getpaid re-exports core types correctly."""

    def test_reexports_core_enums(self):
        """Core enums should be importable from getpaid."""
        import getpaid

        assert hasattr(getpaid, 'BackendMethod')
        assert hasattr(getpaid, 'ConfirmationMethod')
        assert hasattr(getpaid, 'FraudEvent')
        assert hasattr(getpaid, 'PaymentEvent')

    def test_reexports_core_exceptions(self):
        """Core exceptions should be importable from getpaid."""
        import getpaid

        assert hasattr(getpaid, 'ChargeFailure')
        assert hasattr(getpaid, 'CommunicationError')
        assert hasattr(getpaid, 'CredentialsError')
        assert hasattr(getpaid, 'GetPaidException')
        assert hasattr(getpaid, 'InvalidCallbackError')
        assert hasattr(getpaid, 'InvalidTransitionError')
        assert hasattr(getpaid, 'LockFailure')
        assert hasattr(getpaid, 'RefundFailure')

    def test_reexports_core_classes(self):
        """Core classes should be importable from getpaid."""
        import getpaid

        assert hasattr(getpaid, 'PaymentFlow')
        assert hasattr(getpaid, 'BaseProcessor')
        assert hasattr(getpaid, 'PluginRegistry')
        assert hasattr(getpaid, 'registry')

    def test_reexports_core_types(self):
        """Core types should be importable from getpaid."""
        import getpaid

        assert hasattr(getpaid, 'BuyerInfo')
        assert hasattr(getpaid, 'ChargeResult')
        assert hasattr(getpaid, 'ItemInfo')
        assert hasattr(getpaid, 'PaymentUpdate')
        assert hasattr(getpaid, 'RefundResult')
        assert hasattr(getpaid, 'TransactionResult')

    def test_registry_is_core_type(self):
        """The core registry re-export should be the core PluginRegistry."""
        from getpaid_core.registry import PluginRegistry

        import getpaid

        assert isinstance(getpaid.core_registry, PluginRegistry)

    def test_base_processor_is_core(self):
        """BaseProcessor should be the core class."""
        from getpaid_core.processor import BaseProcessor as CoreBP

        import getpaid

        assert getpaid.BaseProcessor is CoreBP
