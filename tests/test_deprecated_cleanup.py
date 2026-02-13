"""Tests for deprecated API cleanup (Phase 5).

Ensures that:
- No `default_app_config` in __init__.py files
- No `typing_extensions` dependency for TypedDict
- No try/except fallback for classproperty
- AppConfig classes set `default_auto_field`
"""

import importlib
import inspect


class TestNoDefaultAppConfig:
    """default_app_config is deprecated since Django 3.2 and no-op in 6.0."""

    def test_getpaid_init_no_default_app_config(self):
        import getpaid

        assert not hasattr(getpaid, 'default_app_config') or (
            'default_app_config' not in inspect.getsource(getpaid)
        )

    def test_dummy_backend_init_no_default_app_config(self):
        import getpaid.backends.dummy

        source = inspect.getsource(getpaid.backends.dummy)
        assert 'default_app_config' not in source


class TestNoTypingExtensions:
    """TypedDict is in stdlib since Python 3.8; typing_extensions is unnecessary."""

    def test_types_module_uses_stdlib_typeddict(self):
        source_file = importlib.import_module('getpaid.types').__file__
        with open(source_file) as f:
            source = f.read()
        assert 'typing_extensions' not in source
        assert 'from typing import' in source or 'typing.TypedDict' in source


class TestNoClasspropertyFallback:
    """classproperty is in django.utils.functional since Django 3.1."""

    def test_types_module_no_try_except_classproperty(self):
        source_file = importlib.import_module('getpaid.types').__file__
        with open(source_file) as f:
            source = f.read()
        assert 'django.utils.decorators' not in source
        assert 'from django.utils.functional import classproperty' in source


class TestDefaultAutoField:
    """AppConfig classes should set default_auto_field."""

    def test_getpaid_appconfig_has_default_auto_field(self):
        from getpaid.apps import GetpaidConfig

        assert hasattr(GetpaidConfig, 'default_auto_field')
        assert GetpaidConfig.default_auto_field is not None

    def test_dummy_appconfig_has_default_auto_field(self):
        from getpaid.backends.dummy.apps import DummyPluginAppConfig

        assert hasattr(DummyPluginAppConfig, 'default_auto_field')
        assert DummyPluginAppConfig.default_auto_field is not None


class TestNoPhantomDependencies:
    """Verify no imports of declared-but-unused dependencies in library code."""

    def _collect_library_sources(self):
        """Collect all Python source files in getpaid/ package."""
        import pathlib

        getpaid_root = pathlib.Path(
            importlib.import_module('getpaid').__file__
        ).parent
        return list(getpaid_root.rglob('*.py'))

    def test_no_pendulum_import(self):
        """pendulum should not be imported anywhere in getpaid/."""
        for path in self._collect_library_sources():
            source = path.read_text()
            assert 'import pendulum' not in source, (
                f'Found pendulum import in {path}'
            )

    def test_no_django_model_utils_import(self):
        """django-model-utils should not be imported anywhere in getpaid/."""
        for path in self._collect_library_sources():
            source = path.read_text()
            assert 'import model_utils' not in source, (
                f'Found model_utils import in {path}'
            )
            assert 'from model_utils' not in source, (
                f'Found model_utils import in {path}'
            )

    def test_no_requests_import_in_library(self):
        """requests should not be imported in the core library or dummy backend."""
        for path in self._collect_library_sources():
            source = path.read_text()
            # Check for direct 'import requests' or 'from requests'
            for line in source.splitlines():
                stripped = line.strip()
                if stripped.startswith('#'):
                    continue
                assert not (
                    stripped.startswith('import requests')
                    or stripped.startswith('from requests')
                ), f'Found requests import in {path}: {stripped}'

    def test_pyproject_declares_django_dependency(self):
        """pyproject.toml should declare Django as a dependency."""
        import pathlib

        pyproject_path = (
            pathlib.Path(
                importlib.import_module('getpaid').__file__
            ).parent.parent
            / 'pyproject.toml'
        )
        source = pyproject_path.read_text()
        # Should have Django in dependencies (case insensitive check)
        assert 'django' in source.lower() or 'Django' in source

    def test_pyproject_no_pendulum_dependency(self):
        """pyproject.toml should not declare pendulum as a dependency."""
        import pathlib

        pyproject_path = (
            pathlib.Path(
                importlib.import_module('getpaid').__file__
            ).parent.parent
            / 'pyproject.toml'
        )
        source = pyproject_path.read_text()
        # Should not have pendulum in [tool.poetry.dependencies]
        in_deps = False
        for line in source.splitlines():
            if '[tool.poetry.dependencies]' in line:
                in_deps = True
                continue
            if in_deps and line.startswith('['):
                break
            if in_deps and 'pendulum' in line.lower():
                assert False, f'pendulum still in dependencies: {line}'

    def test_pyproject_no_django_model_utils_dependency(self):
        """pyproject.toml should not declare django-model-utils as a dependency."""
        import pathlib

        pyproject_path = (
            pathlib.Path(
                importlib.import_module('getpaid').__file__
            ).parent.parent
            / 'pyproject.toml'
        )
        source = pyproject_path.read_text()
        in_deps = False
        for line in source.splitlines():
            if '[tool.poetry.dependencies]' in line:
                in_deps = True
                continue
            if in_deps and line.startswith('['):
                break
            if in_deps and 'django-model-utils' in line.lower():
                assert False, (
                    f'django-model-utils still in dependencies: {line}'
                )

    def test_pyproject_no_typing_extensions_dependency(self):
        """pyproject.toml should not declare typing-extensions as a dependency."""
        import pathlib

        pyproject_path = (
            pathlib.Path(
                importlib.import_module('getpaid').__file__
            ).parent.parent
            / 'pyproject.toml'
        )
        source = pyproject_path.read_text()
        in_deps = False
        for line in source.splitlines():
            if '[tool.poetry.dependencies]' in line:
                in_deps = True
                continue
            if in_deps and line.startswith('['):
                break
            if in_deps and 'typing-extensions' in line.lower():
                assert False, f'typing-extensions still in dependencies: {line}'


class TestStatusCompat:
    """getpaid.status should still re-export symbols for backward compat."""

    def test_status_exports_payment_status(self):
        from getpaid.status import PaymentStatus
        from getpaid.types import PaymentStatus as PS

        assert PaymentStatus is PS

    def test_status_exports_fraud_status(self):
        from getpaid.status import FraudStatus
        from getpaid.types import FraudStatus as FS

        assert FraudStatus is FS
