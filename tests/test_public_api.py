"""Tests for the public package API."""

import re
import tomllib
from importlib import metadata
from pathlib import Path

import getpaid_core
import getpaid_paynow

import getpaid


def _pyproject() -> dict:
    return tomllib.loads(Path('pyproject.toml').read_text())


def _version_tuple(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in re.split(r'[.\-+]', version)[:3])


def _floor(requirements: list[str], name: str) -> str:
    """Extract the `>=` floor for a requirement from a dependency list."""
    for requirement in requirements:
        match = re.fullmatch(rf'{re.escape(name)}>=([\w.\-]+)', requirement)
        if match:
            return match.group(1)
    raise AssertionError(f'No >= floor declared for {name!r}')


def test_version_matches_installed_metadata() -> None:
    """Source __version__ must match the installed package metadata."""
    assert getpaid.__version__ == metadata.version('django-getpaid')


def test_core_dependency_floor() -> None:
    """Core floor must be declared and not exceed the current version."""
    current = _version_tuple(getpaid.__version__)
    pyproject_data = _pyproject()

    runtime_floor = _floor(
        pyproject_data['project']['dependencies'], 'python-getpaid-core'
    )
    dev_floor = _floor(
        pyproject_data['dependency-groups']['dev'], 'python-getpaid-core'
    )

    assert _version_tuple(runtime_floor) <= current
    assert _version_tuple(dev_floor) <= current
    # Floors must stay on the same major line as the package itself.
    assert _version_tuple(runtime_floor)[0] == current[0]


def test_paynow_dev_dependency_floor() -> None:
    current = _version_tuple(getpaid.__version__)
    pyproject_data = _pyproject()

    dev_floor = _floor(
        pyproject_data['dependency-groups']['dev'], 'python-getpaid-paynow'
    )

    assert _version_tuple(dev_floor) <= current
    assert _version_tuple(dev_floor)[0] == current[0]


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
