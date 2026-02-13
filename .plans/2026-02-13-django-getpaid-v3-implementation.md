# django-getpaid v3 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rewrite django-getpaid as a thin adapter over getpaid-core, replacing django-fsm with core's transitions-based FSM while preserving Django model/view/form/admin integration and backward compatibility for users.

**Architecture:** Thin Django adapter wrapping getpaid-core. Models become plain Django models (no ConcurrentTransitionMixin, no FSMField). FSM is attached at runtime via `create_payment_machine()` / `create_fraud_machine()`. Views delegate to flow logic. The Django adapter is sync-first, wrapping core's async methods with `asgiref.async_to_sync`.

**Tech Stack:** Python 3.12+, Django 5.2+, getpaid-core>=0.1.0, swapper>=1.4, transitions (via getpaid-core), uv (dependency management)

**Branch:** `feat/v3-core-adapter` (from `master`)

**Run tests:** `PYTHONPATH=.:example DJANGO_SETTINGS_MODULE=tests.settings python -m pytest tests/ -v`

**IMPORTANT NOTES:**
- Commit with `--no-verify` (pre-commit hook not in PATH in the environment)
- The getpaid-core package is at `../getpaid-core/` and must be installed as a path dependency during development
- The `example/` directory contains the test app (orders, paywall) and must be on PYTHONPATH
- Tests use `pytest-factoryboy` with factories registered in `tests/conftest.py`
- The dummy backend in v2 uses `django_fsm.can_proceed` -- this must be replaced
- v2's `BaseProcessor.__init__(self, payment)` has only `payment` arg; core's has `(self, payment, config=None)`. The Django adapter's `BaseProcessor` must bridge this.

---

### Task 1: Create feature branch and update pyproject.toml

**Files:**
- Modify: `pyproject.toml`

**Step 1: Create feature branch**

```bash
git checkout -b feat/v3-core-adapter
```

**Step 2: Update pyproject.toml**

Replace the entire `pyproject.toml` with the v3 version. Key changes:
- Add `[build-system]` using hatchling
- Add runtime dependencies: `Django>=5.2`, `swapper>=1.4`, `getpaid-core>=0.1.0`
- Add getpaid-core as path dependency for development
- Remove `django-fsm` (it was never declared but was imported)
- Update version to `3.0.0a1`
- Keep existing ruff config
- Add `[tool.pytest.ini_options]`

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "django-getpaid"
version = "3.0.0a1"
description = "Multi-broker payment processor for Django."
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
    "Django>=5.2",
    "swapper>=1.4",
    "getpaid-core>=0.1.0",
]

[dependency-groups]
dev = [
    "django>=6.0.2",
    "httpx>=0.28.1",
    "pre-commit>=4.5.1",
    "pre-commit-hooks>=6.0.0",
    "pytest>=9.0.2",
    "pytest-asyncio>=1.3.0",
    "pytest-cov>=7.0.0",
    "pytest-django>=4.11.1",
    "pytest-factoryboy>=2.8.1",
    "ruff>=0.15.1",
    "tox>=4.35.0",
    "ty>=0.0.16",
    "getpaid-core @ file:///${PROJECT_ROOT}/../getpaid-core",
]

[tool.pytest.ini_options]
DJANGO_SETTINGS_MODULE = "tests.settings"
pythonpath = [".", "example"]
asyncio_mode = "auto"

[tool.hatch.build.targets.wheel]
packages = ["getpaid"]

# --- Ruff config (unchanged) ---
[tool.ruff]
preview = true
fix = true
target-version = "py312"
line-length = 80

[tool.ruff.format]
quote-style = "single"
docstring-code-format = true

[tool.ruff.lint]
select = [
  "A",    # flake8-builtins
  "B",    # flake8-bugbear
  "C4",   # flake8-comprehensions
  "C90",  # maccabe
  "COM",  # flake8-commas
  "DTZ",  # flake8-datetimez
  "EXE",  # flake8-executable
  "F",    # pyflakes
  "FBT",  # flake8-boolean-trap
  "FLY",  # pyflint
  "FURB", # refurb
  "I",    # isort
  "ICN",  # flake8-import-conventions
  "ISC",  # flake8-implicit-str-concat
  "LOG",  # flake8-logging
  "N",    # pep8-naming
  "PERF", # perflint
  "PIE",  # flake8-pie
  "PL",   # pylint
  "PT",   # flake8-pytest-style
  "PTH",  # flake8-use-pathlib
  "Q",    # flake8-quotes
  "RET",  # flake8-return
  "RSE",  # flake8-raise
  "RUF",  # ruff
  "S",    # flake8-bandit
  "SIM",  # flake8-simpify
  "SLF",  # flake8-self
  "SLOT", # flake8-slots
  "T100", # flake8-debugger
  "TRY",  # tryceratops
  "UP",   # pyupgrade
  "W",    # pycodestyle
  "YTT",  # flake8-2020
]
ignore = [
  "A005",
  "COM812",
  "D100",
  "D104",
  "D106",
  "D203",
  "D212",
  "D401",
  "D404",
  "D405",
  "ISC001",
  "ISC003",
  "PLR09",
  "PLR2004",
  "PLR6301",
  "TRY003",
  "RUF012",
]
external = [ "WPS" ]
flake8-quotes.inline-quotes = "single"
mccabe.max-complexity = 9
pydocstyle.convention = "google"

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101"]
```

**Step 3: Install dependencies**

```bash
uv sync
```

Expected: All deps install, including getpaid-core from local path.

**Step 4: Verify tests still run (they will fail because django-fsm is gone, but import should work)**

```bash
PYTHONPATH=.:example DJANGO_SETTINGS_MODULE=tests.settings python -c "import getpaid; print(getpaid.__version__)"
```

Expected: Prints version. May show import errors for django_fsm which is expected — we'll fix those next.

**Step 5: Commit**

```bash
git add pyproject.toml
git commit --no-verify -m "chore: update pyproject.toml for v3 (add getpaid-core dep, hatchling build)"
```

---

### Task 2: Re-export core enums, types, and exceptions

Replace `getpaid/types.py`, `getpaid/exceptions.py`, and `getpaid/status.py` with thin re-exports from getpaid-core. The Django-specific enum behavior (`choices`/`CHOICES` properties using `pgettext_lazy`) needs a Django wrapper that extends the core enums.

**Files:**
- Modify: `getpaid/types.py`
- Modify: `getpaid/exceptions.py`
- Modify: `getpaid/status.py`
- Modify: `getpaid/__init__.py`

**Step 1: Write a test to verify core re-exports work**

Create `tests/test_reexports.py`:

```python
"""Tests that getpaid re-exports core types correctly."""

from getpaid_core.enums import PaymentStatus as CorePS
from getpaid_core.enums import FraudStatus as CoreFS
from getpaid_core.exceptions import GetPaidException as CoreGPE

from getpaid.types import PaymentStatus, FraudStatus
from getpaid.types import BuyerInfo, ItemInfo, ChargeResponse
from getpaid.types import BackendMethod, ConfirmationMethod
from getpaid.exceptions import (
    GetPaidException,
    ChargeFailure,
    CommunicationError,
    CredentialsError,
    LockFailure,
    RefundFailure,
)
from getpaid.status import PaymentStatus as StatusPS
from getpaid.status import FraudStatus as StatusFS


class TestEnumReExports:
    def test_payment_status_values_match_core(self):
        """PaymentStatus values must exactly match core."""
        assert PaymentStatus.NEW == CorePS.NEW
        assert PaymentStatus.PRE_AUTH == CorePS.PRE_AUTH
        assert PaymentStatus.PRE_AUTH == 'pre-auth'
        assert PaymentStatus.IN_CHARGE == CorePS.IN_CHARGE
        assert PaymentStatus.IN_CHARGE == 'charge_started'
        assert PaymentStatus.PARTIAL == CorePS.PARTIAL
        assert PaymentStatus.PARTIAL == 'partially_paid'

    def test_fraud_status_values_match_core(self):
        assert FraudStatus.UNKNOWN == CoreFS.UNKNOWN
        assert FraudStatus.ACCEPTED == CoreFS.ACCEPTED

    def test_payment_status_has_choices(self):
        """Django wrapper must provide .choices and .CHOICES."""
        choices = PaymentStatus.choices
        assert isinstance(choices, tuple)
        assert len(choices) == 9
        # Each choice is (value, label) tuple
        for value, label in choices:
            assert isinstance(value, str)

    def test_fraud_status_has_choices(self):
        choices = FraudStatus.choices
        assert isinstance(choices, tuple)
        assert len(choices) == 4

    def test_choices_backward_compat(self):
        """CHOICES (uppercase) must equal choices."""
        assert PaymentStatus.CHOICES == PaymentStatus.choices
        assert FraudStatus.CHOICES == FraudStatus.choices

    def test_status_compat_module(self):
        """getpaid.status should re-export the same classes."""
        assert StatusPS is PaymentStatus
        assert StatusFS is FraudStatus


class TestExceptionReExports:
    def test_getpaid_exception_inherits_core(self):
        """Our GetPaidException should be the core one."""
        assert GetPaidException is CoreGPE or issubclass(
            GetPaidException, CoreGPE
        )

    def test_charge_failure_is_communication_error(self):
        assert issubclass(ChargeFailure, CommunicationError)

    def test_lock_failure_is_communication_error(self):
        assert issubclass(LockFailure, CommunicationError)

    def test_refund_failure_is_communication_error(self):
        assert issubclass(RefundFailure, CommunicationError)

    def test_exception_accepts_context_kwarg(self):
        """Backward compat: context kwarg must work."""
        exc = GetPaidException('test', context={'key': 'val'})
        assert exc.context == {'key': 'val'}


class TestTypeReExports:
    def test_buyer_info_is_typed_dict(self):
        info: BuyerInfo = {'email': 'a@b.com'}
        assert 'email' in info

    def test_item_info(self):
        from decimal import Decimal
        item: ItemInfo = {'name': 'x', 'quantity': 1, 'unit_price': Decimal('10')}
        assert item['name'] == 'x'

    def test_backend_method_enum(self):
        assert BackendMethod.GET == 'GET'
        assert BackendMethod.POST == 'POST'
        assert BackendMethod.REST == 'REST'

    def test_confirmation_method_enum(self):
        assert ConfirmationMethod.PUSH == 'PUSH'
        assert ConfirmationMethod.PULL == 'PULL'
```

**Step 2: Run test to verify it fails**

```bash
PYTHONPATH=.:example DJANGO_SETTINGS_MODULE=tests.settings python -m pytest tests/test_reexports.py -v
```

Expected: FAIL — current code imports from django_fsm, and enums don't use StrEnum.

**Step 3: Rewrite getpaid/types.py**

```python
"""Payment types and enums.

Wraps getpaid-core enums with Django-specific features (choices property).
Re-exports core types unchanged.
"""

from decimal import Decimal
from typing import Any, TypedDict

from django.http import HttpResponse
from django.utils.functional import classproperty
from django.utils.translation import pgettext_lazy

from getpaid_core.enums import (
    BackendMethod,
    ConfirmationMethod,
)
from getpaid_core.enums import FraudStatus as _CoreFraudStatus
from getpaid_core.enums import PaymentStatus as _CorePaymentStatus
from getpaid_core.types import BuyerInfo, ChargeResponse, ItemInfo

# Re-export core types directly
__all__ = [
    'BackendMethod',
    'BuyerInfo',
    'ChargeResponse',
    'ConfirmationMethod',
    'FraudStatus',
    'ItemInfo',
    'PaymentStatus',
    'PaymentStatusResponse',
    'RestfulResult',
]


class PaymentStatus(_CorePaymentStatus):
    """PaymentStatus with Django choices support."""

    @classproperty
    def choices(cls):
        return (
            (cls.NEW.value, pgettext_lazy('payment status', 'new')),
            (
                cls.PREPARED.value,
                pgettext_lazy('payment status', 'in progress'),
            ),
            (cls.PRE_AUTH.value, pgettext_lazy('payment status', 'pre-authed')),
            (
                cls.IN_CHARGE.value,
                pgettext_lazy('payment status', 'charge process started'),
            ),
            (
                cls.PARTIAL.value,
                pgettext_lazy('payment status', 'partially paid'),
            ),
            (cls.PAID.value, pgettext_lazy('payment status', 'paid')),
            (cls.FAILED.value, pgettext_lazy('payment status', 'failed')),
            (
                cls.REFUND_STARTED.value,
                pgettext_lazy('payment status', 'refund started'),
            ),
            (cls.REFUNDED.value, pgettext_lazy('payment status', 'refunded')),
        )

    @classproperty
    def CHOICES(cls):
        """Backward compatibility."""
        return cls.choices


class FraudStatus(_CoreFraudStatus):
    """FraudStatus with Django choices support."""

    @classproperty
    def choices(cls):
        return (
            (cls.UNKNOWN.value, pgettext_lazy('fraud status', 'unknown')),
            (cls.ACCEPTED.value, pgettext_lazy('fraud status', 'accepted')),
            (cls.REJECTED.value, pgettext_lazy('fraud status', 'rejected')),
            (
                cls.CHECK.value,
                pgettext_lazy('fraud status', 'needs manual verification'),
            ),
        )

    @classproperty
    def CHOICES(cls):
        """Backward compatibility."""
        return cls.choices


class GetpaidInternalResponse(TypedDict):
    raw_response: Any
    exception: Exception | None


class PaymentStatusResponse(GetpaidInternalResponse):
    amount: Decimal | None
    callback: str | None
    callback_result: Any | None
    saved: bool | None


class FormField(TypedDict):
    name: str
    value: Any
    label: str | None
    widget: str
    help_text: str | None
    required: bool


class PaymentForm(TypedDict):
    fields: list[FormField]


class RestfulResult(TypedDict):
    status_code: int
    result: HttpResponse
    target_url: str | None
    form: PaymentForm | None
    message: str | bytes | None
```

**Step 4: Rewrite getpaid/exceptions.py**

```python
"""Exception hierarchy -- re-exports from getpaid-core."""

from getpaid_core.exceptions import (
    ChargeFailure,
    CommunicationError,
    CredentialsError,
    GetPaidException,
    InvalidCallbackError,
    InvalidTransitionError,
    LockFailure,
    RefundFailure,
)

__all__ = [
    'ChargeFailure',
    'CommunicationError',
    'CredentialsError',
    'GetPaidException',
    'InvalidCallbackError',
    'InvalidTransitionError',
    'LockFailure',
    'RefundFailure',
]
```

**Step 5: Update getpaid/status.py**

```python
from .types import FraudStatus, PaymentStatus  # noqa: F401
```

(Unchanged — already correct since it imports from `.types`.)

**Step 6: Update getpaid/__init__.py**

```python
from .types import FraudStatus, PaymentStatus  # noqa: F401

__version__ = '3.0.0a1'
```

**Step 7: Run test**

```bash
PYTHONPATH=.:example DJANGO_SETTINGS_MODULE=tests.settings python -m pytest tests/test_reexports.py -v
```

Expected: ALL PASS

**Step 8: Commit**

```bash
git add getpaid/types.py getpaid/exceptions.py getpaid/status.py getpaid/__init__.py tests/test_reexports.py
git commit --no-verify -m "refactor: re-export enums, types, exceptions from getpaid-core"
```

---

### Task 3: Replace Django registry with core registry adapter

The Django `PluginRegistry` needs to wrap `getpaid_core.registry.PluginRegistry` but add Django-specific features: URL generation, `get_choices()` returning `(module_path, display_name)` tuples (not just slug), and `register(module_or_proc)` that handles both module and class registration.

**Files:**
- Modify: `getpaid/registry.py`
- Create: `tests/test_registry_v3.py`

**Step 1: Write tests for the new registry adapter**

Create `tests/test_registry_v3.py`:

```python
"""Tests for Django registry adapter wrapping getpaid-core."""

import pytest

from getpaid.registry import registry, DjangoPluginRegistry
from getpaid_core.registry import registry as core_registry


class TestDjangoRegistryAdapter:
    def test_registry_is_django_wrapper(self):
        assert isinstance(registry, DjangoPluginRegistry)

    def test_register_class_directly(self):
        from tests.tools import Plugin

        # Clear and re-register
        registry.unregister(Plugin.slug)
        registry.register(Plugin)
        assert Plugin.slug in registry
        assert registry[Plugin.slug] is Plugin

    def test_register_module_with_processor_attr(self):
        """Backward compat: register(module) should find module.processor.PaymentProcessor."""
        import types

        mock_proc_module = types.ModuleType('mock_proc')

        from getpaid_core.processor import BaseProcessor

        class MockProcessor(BaseProcessor):
            slug = 'mock_mod_proc'
            display_name = 'Mock'
            accepted_currencies = ['EUR']

            async def prepare_transaction(self, **kwargs):
                return {}

        mock_proc_module.PaymentProcessor = MockProcessor

        mock_module = types.ModuleType('mock_backend')
        mock_module.__name__ = 'mock_backend'
        mock_module.processor = mock_proc_module

        registry.register(mock_module)
        assert 'mock_mod_proc' in registry
        registry.unregister('mock_mod_proc')

    def test_contains(self):
        from tests.tools import Plugin

        registry.register(Plugin)
        assert Plugin.slug in registry

    def test_getitem(self):
        from tests.tools import Plugin

        registry.register(Plugin)
        assert registry[Plugin.slug] is Plugin

    def test_iter(self):
        from tests.tools import Plugin

        registry.register(Plugin)
        slugs = list(registry)
        assert Plugin.slug in slugs

    def test_get_choices(self):
        from tests.tools import Plugin

        registry.register(Plugin)
        choices = registry.get_choices('EUR')
        assert any(slug == Plugin.slug for slug, _name in choices)

    def test_get_backends(self):
        from tests.tools import Plugin

        registry.register(Plugin)
        backends = registry.get_backends('EUR')
        assert Plugin in backends

    def test_get_all_supported_currency_choices(self):
        from tests.tools import Plugin

        registry.register(Plugin)
        choices = registry.get_all_supported_currency_choices()
        codes = {c for c, _ in choices}
        assert 'EUR' in codes
        assert 'USD' in codes

    @pytest.mark.django_db
    def test_urls_property(self):
        """urls property should return URL patterns for backends with urls modules."""
        urls = registry.urls
        assert isinstance(urls, list)
```

**Step 2: Run test to verify it fails**

```bash
PYTHONPATH=.:example DJANGO_SETTINGS_MODULE=tests.settings python -m pytest tests/test_registry_v3.py -v
```

Expected: FAIL — `DjangoPluginRegistry` doesn't exist yet.

**Step 3: Rewrite getpaid/registry.py**

```python
"""Django-specific plugin registry wrapping getpaid-core."""

import importlib

from django.urls import include, path

from getpaid_core.processor import BaseProcessor
from getpaid_core.registry import PluginRegistry as CorePluginRegistry


def _importable(name):
    try:
        importlib.import_module(name)
        return True
    except ImportError:
        return False


class DjangoPluginRegistry:
    """Django adapter for getpaid-core's PluginRegistry.

    Adds Django-specific features: URL generation, module-based
    registration (backward compat), and CHOICES-format helpers.
    """

    def __init__(self, core_registry: CorePluginRegistry) -> None:
        self._core = core_registry
        # Map from module path -> slug for backward compat
        self._module_map: dict[str, str] = {}

    def __contains__(self, item):
        return (
            item in self._module_map or self._has_slug(item)
        )

    def __getitem__(self, item):
        slug = self._module_map.get(item, item)
        return self._core.get_by_slug(slug)

    def __iter__(self):
        return iter(self._all_keys())

    def register(self, module_or_proc):
        """Register a backend by class or module (backward compat).

        Supports:
        - register(ProcessorClass) -- direct class registration
        - register(module) -- finds module.processor.PaymentProcessor
        """
        if isinstance(module_or_proc, type) and issubclass(
            module_or_proc, BaseProcessor
        ):
            self._core.register(module_or_proc)
            return

        # Module-based registration (v2 backward compat)
        processor = module_or_proc.processor.PaymentProcessor
        self._core.register(processor)
        self._module_map[module_or_proc.__name__] = processor.slug

    def unregister(self, slug_or_module_path: str):
        """Remove a backend by slug or module path."""
        slug = self._module_map.pop(slug_or_module_path, slug_or_module_path)
        self._core.unregister(slug)

    def get_choices(self, currency):
        """Get CHOICES for plugins supporting given currency."""
        return self._core.get_choices(currency.upper())

    def get_backends(self, currency):
        """Get backend classes supporting given currency."""
        return self._core.get_for_currency(currency.upper())

    @property
    def urls(self):
        """Provide URL structure for registered plugins with urls modules."""
        result = []
        for module_path, slug in self._module_map.items():
            urls_module = f'{module_path}.urls'
            if _importable(urls_module):
                proc_class = self._core.get_by_slug(slug)
                result.append(
                    path(
                        f'{proc_class.slug}/',
                        include(
                            (urls_module, proc_class.slug),
                            namespace=proc_class.slug,
                        ),
                    )
                )
        # Also check direct slug registrations
        for slug in self._core._backends:
            if slug not in self._module_map.values():
                # Try to find a urls module by convention
                pass  # Direct class registrations don't have urls
        return result

    def get_all_supported_currency_choices(self):
        """Get all currencies supported by any plugin, as CHOICES."""
        currencies = self._core.get_all_currencies()
        return [(c.upper(), c.upper()) for c in currencies]

    def _has_slug(self, item):
        try:
            self._core.get_by_slug(item)
            return True
        except KeyError:
            return False

    def _all_keys(self):
        """Return all keys (both module paths and slugs)."""
        keys = set(self._module_map.keys())
        keys.update(self._core._backends.keys())
        return keys


# Module-level singleton wrapping core's singleton
registry = DjangoPluginRegistry(CorePluginRegistry())
```

**Step 4: Run test**

```bash
PYTHONPATH=.:example DJANGO_SETTINGS_MODULE=tests.settings python -m pytest tests/test_registry_v3.py -v
```

Expected: ALL PASS

**Step 5: Commit**

```bash
git add getpaid/registry.py tests/test_registry_v3.py
git commit --no-verify -m "refactor: replace Django registry with core registry adapter"
```

---

### Task 4: Rewrite BaseProcessor adapter for Django

The v2 `BaseProcessor` must continue working as the base class for Django backends (dummy, external plugins). It needs to bridge v2's `__init__(self, payment)` signature with core's `__init__(self, payment, config=None)`, while keeping Django-specific helpers (get_our_baseurl, get_template_names, get_form, get_setting with Django settings).

**Files:**
- Modify: `getpaid/processor.py`
- Modify: `tests/tools.py`

**Step 1: Write tests for the Django processor adapter**

Create `tests/test_processor_v3.py`:

```python
"""Tests for Django BaseProcessor adapter."""

from unittest.mock import MagicMock

import pytest

from getpaid.processor import BaseProcessor
from getpaid_core.processor import BaseProcessor as CoreBaseProcessor


class TestProcessorInheritance:
    def test_inherits_core(self):
        """Django BaseProcessor must be a subclass of core BaseProcessor."""
        assert issubclass(BaseProcessor, CoreBaseProcessor)

    def test_init_with_payment_only(self):
        """v2 compat: __init__(payment) without config should work."""
        mock_payment = MagicMock()
        mock_payment.backend = 'test'

        class TestProc(BaseProcessor):
            slug = 'test_init'
            display_name = 'Test'
            accepted_currencies = ['EUR']

            async def prepare_transaction(self, **kwargs):
                return {}

        proc = TestProc(mock_payment)
        assert proc.payment is mock_payment

    def test_init_reads_django_settings(self, settings):
        """Config should be read from GETPAID_BACKEND_SETTINGS."""
        settings.GETPAID_BACKEND_SETTINGS = {
            'test_backend': {'api_key': 'secret123'}
        }
        settings.GETPAID = {'GLOBAL_OPT': True}

        mock_payment = MagicMock()
        mock_payment.backend = 'test_backend'

        class TestProc(BaseProcessor):
            slug = 'test_settings'
            display_name = 'Test'
            accepted_currencies = ['EUR']

            async def prepare_transaction(self, **kwargs):
                return {}

        proc = TestProc(mock_payment)
        assert proc.get_setting('api_key') == 'secret123'
        assert proc.get_setting('GLOBAL_OPT') is True
        assert proc.get_setting('nonexistent') is None

    def test_class_id(self):
        class TestProc(BaseProcessor):
            slug = 'test_class_id'
            display_name = 'Test'
            accepted_currencies = ['EUR']

            async def prepare_transaction(self, **kwargs):
                return {}

        assert TestProc.class_id() == TestProc.__module__

    @pytest.mark.django_db
    def test_get_our_baseurl_with_request(self, rf, settings):
        settings.DEBUG = True
        request = rf.get('/')
        url = BaseProcessor.get_our_baseurl(request)
        assert url.startswith('http')
        assert url.endswith('/')

    @pytest.mark.django_db
    def test_get_our_baseurl_without_request(self, settings):
        from django.contrib.sites.models import Site

        Site.objects.update_or_create(
            id=settings.SITE_ID,
            defaults={'domain': 'example.com', 'name': 'Example'},
        )
        settings.DEBUG = False
        url = BaseProcessor.get_our_baseurl(request=None)
        assert 'example.com' in url
```

**Step 2: Run test to verify it fails**

```bash
PYTHONPATH=.:example DJANGO_SETTINGS_MODULE=tests.settings python -m pytest tests/test_processor_v3.py -v
```

Expected: FAIL — current BaseProcessor imports from django_fsm (indirectly), doesn't inherit core.

**Step 3: Rewrite getpaid/processor.py**

```python
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

    production_url = None
    sandbox_url = None
    post_form_class = None
    post_template_name = None
    client_class = None
    client = None
    ok_statuses = [200]

    def __init__(self, payment, config=None) -> None:
        # Read config from Django settings if not provided
        if config is None:
            path = getattr(payment, 'backend', '') or ''
            config = getattr(
                settings, 'GETPAID_BACKEND_SETTINGS', {}
            ).get(path, {})
        super().__init__(payment, config=config)
        self.path = getattr(payment, 'backend', '') or ''
        self.context = {}
        if self.slug is None:
            self.slug = self.path
        self.optional_config = getattr(settings, 'GETPAID', {})
        if self.client_class is not None:
            self.client = self.get_client()

    def get_setting(self, name: str, default: Any | None = None) -> Any:
        """Read setting from backend config, falling back to GETPAID global."""
        value = self.config.get(name, default)
        if value is None:
            value = self.optional_config.get(name, None)
        return value

    def get_client_class(self) -> type:
        class_path = self.get_setting('CLIENT_CLASS')
        if not class_path:
            class_path = self.client_class
        if class_path and not callable(class_path):
            module_name, _, class_name = class_path.rpartition('.')
            module = import_module(module_name)
            return getattr(module, class_name)
        return class_path

    def get_client(self) -> object:
        return self.get_client_class()(**self.get_client_params())

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
    def get_logo_url(cls, **kwargs) -> str:
        return cls.logo_url

    @classmethod
    def get_paywall_baseurl(cls, **kwargs) -> str:
        if settings.DEBUG:
            return cls.sandbox_url
        return cls.production_url

    @staticmethod
    def get_our_baseurl(request: HttpRequest = None, **kwargs) -> str:
        """Get base URL for our site.

        Uses Sites framework when no request is available.
        """
        scheme = 'http' if settings.DEBUG else 'https'
        if request is not None:
            domain = get_current_site(request).domain
        else:
            from django.contrib.sites.models import Site

            domain = Site.objects.get_current().domain
        return f'{scheme}://{domain}/'

    def get_template_names(
        self, view: View | None = None, **kwargs
    ) -> list[str]:
        template_name = self.get_setting('POST_TEMPLATE')
        if template_name is None:
            template_name = self.post_template_name
        if template_name is None and hasattr(view, 'get_template_names'):
            return view.get_template_names()
        if template_name is None:
            raise ImproperlyConfigured("Couldn't determine template name!")
        return [template_name]

    def get_form_class(self, **kwargs) -> type:
        form_class_path = self.get_setting('POST_FORM_CLASS')
        if not form_class_path:
            return self.post_form_class
        if isinstance(form_class_path, str):
            module_path, class_name = form_class_path.rsplit('.', 1)
            module = import_module(module_path)
            return getattr(module, class_name)
        return self.post_form_class

    def prepare_form_data(
        self, post_data: dict, **kwargs
    ) -> Mapping[str, Any]:
        return post_data

    def get_form(self, post_data: dict, **kwargs) -> BaseForm:
        form_class = self.get_form_class()
        if form_class is None:
            raise ImproperlyConfigured("Couldn't determine form class!")
        form_data = self.prepare_form_data(post_data)
        return form_class(fields=form_data)

    # verify_callback with Django HttpRequest signature (backward compat)
    def verify_callback_request(
        self, request: HttpRequest, **kwargs
    ) -> None:
        """Verify callback from Django request. Override in backends.

        Default: no-op (accepts all callbacks).
        """
```

**Step 4: Update tests/tools.py to use new BaseProcessor**

```python
from getpaid.processor import BaseProcessor


class Plugin(BaseProcessor):
    display_name = 'Test plugin'
    accepted_currencies = ['EUR', 'USD']
    slug = 'test_plugin'

    async def prepare_transaction(self, **kwargs):
        return {}
```

**Step 5: Run tests**

```bash
PYTHONPATH=.:example DJANGO_SETTINGS_MODULE=tests.settings python -m pytest tests/test_processor_v3.py -v
```

Expected: ALL PASS

**Step 6: Commit**

```bash
git add getpaid/processor.py tests/tools.py tests/test_processor_v3.py
git commit --no-verify -m "refactor: rewrite BaseProcessor as Django adapter over core"
```

---

### Task 5: Rewrite AbstractPayment model (core task)

This is the biggest change. Replace `ConcurrentTransitionMixin`, `FSMField`, and `@transition` decorators with plain Django model fields and runtime FSM attachment.

**Files:**
- Modify: `getpaid/abstracts.py`

**Step 1: Write tests for the new model**

Create `tests/test_model_v3.py`:

```python
"""Tests for AbstractPayment v3 (no django-fsm, uses getpaid-core FSM)."""

import logging
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
import swapper

from getpaid.types import FraudStatus as fs
from getpaid.types import PaymentStatus as ps
from getpaid_core.fsm import create_payment_machine, create_fraud_machine

pytestmark = pytest.mark.django_db

Order = swapper.load_model('getpaid', 'Order')
Payment = swapper.load_model('getpaid', 'Payment')


def _make_payment(**kwargs):
    order = Order.objects.create()
    defaults = {
        'order': order,
        'currency': order.currency,
        'amount_required': Decimal(str(order.get_total_amount())),
        'backend': 'getpaid.backends.dummy',
        'description': order.get_description(),
    }
    defaults.update(kwargs)
    return Payment.objects.create(**defaults)


class TestPaymentModelFields:
    def test_status_is_charfield(self):
        """status should be a CharField, not FSMField."""
        field = Payment._meta.get_field('status')
        assert field.__class__.__name__ == 'CharField'

    def test_fraud_status_is_charfield(self):
        field = Payment._meta.get_field('fraud_status')
        assert field.__class__.__name__ == 'CharField'

    def test_default_status_is_new(self):
        payment = _make_payment()
        assert payment.status == ps.NEW

    def test_default_fraud_status_is_unknown(self):
        payment = _make_payment()
        assert payment.fraud_status == fs.UNKNOWN

    def test_no_concurrent_transition_mixin(self):
        """Model should NOT inherit from ConcurrentTransitionMixin."""
        assert 'ConcurrentTransitionMixin' not in [
            c.__name__ for c in Payment.__mro__
        ]


class TestPaymentFSMAttachment:
    def test_fsm_attaches_transition_methods(self):
        """create_payment_machine should attach trigger methods."""
        payment = _make_payment()
        create_payment_machine(payment)
        assert hasattr(payment, 'confirm_prepared')
        assert callable(payment.confirm_prepared)

    def test_fsm_transition_works(self):
        payment = _make_payment()
        create_payment_machine(payment)
        payment.confirm_prepared()
        assert payment.status == ps.PREPARED

    def test_fraud_fsm_attaches(self):
        payment = _make_payment()
        create_fraud_machine(payment)
        assert hasattr(payment, 'flag_as_fraud')
        payment.flag_as_fraud()
        assert payment.fraud_status == fs.REJECTED


class TestPaymentHelpers:
    def test_get_unique_id(self):
        payment = _make_payment()
        assert payment.get_unique_id() == str(payment.id)

    def test_get_items_delegates_to_order(self):
        payment = _make_payment()
        items = payment.get_items()
        assert len(items) == 1
        assert items[0]['name'] == payment.order.get_description()

    def test_get_buyer_info_delegates_to_order(self):
        payment = _make_payment()
        info = payment.get_buyer_info()
        assert 'email' in info

    def test_fully_paid_property(self):
        payment = _make_payment()
        assert not payment.fully_paid
        payment.amount_paid = payment.amount_required
        assert payment.fully_paid

    def test_is_fully_paid_method(self):
        """is_fully_paid() needed by core FSM guard."""
        payment = _make_payment()
        assert not payment.is_fully_paid()
        payment.amount_paid = payment.amount_required
        assert payment.is_fully_paid()

    def test_is_fully_refunded_method(self):
        """is_fully_refunded() needed by core FSM guard."""
        payment = _make_payment()
        payment.amount_paid = Decimal('100')
        payment.amount_refunded = Decimal('100')
        assert payment.is_fully_refunded()

    def test_str(self):
        payment = _make_payment()
        assert str(payment).startswith('Payment #')
```

**Step 2: Run test to verify it fails**

```bash
PYTHONPATH=.:example DJANGO_SETTINGS_MODULE=tests.settings python -m pytest tests/test_model_v3.py -v
```

Expected: FAIL — still imports django_fsm.

**Step 3: Rewrite getpaid/abstracts.py**

```python
"""Abstract models for django-getpaid v3.

Models are plain Django models. FSM is attached at runtime
via getpaid-core's create_payment_machine() / create_fraud_machine().
"""

import logging
import uuid
from decimal import Decimal

import swapper
from django import forms
from django.db import models
from django.http import HttpRequest
from django.shortcuts import resolve_url
from django.utils.translation import gettext_lazy as _

from getpaid.exceptions import GetPaidException
from getpaid.types import BuyerInfo, ItemInfo
from getpaid.types import FraudStatus as fs
from getpaid.types import PaymentStatus as ps

logger = logging.getLogger(__name__)


class AbstractOrder(models.Model):
    """Base class for Order models.

    Consider using UUIDField as primary or secondary key to hide volume.
    """

    class Meta:
        abstract = True

    def get_return_url(
        self,
        *args,
        success: bool | None = None,
        **kwargs,
    ) -> str:
        """Return URL after payment completion.

        Override to customize. Default: get_absolute_url().
        """
        return self.get_absolute_url()

    def get_absolute_url(self) -> str:
        raise NotImplementedError

    def is_ready_for_payment(self) -> bool:
        """Validate order is ready for payment.

        Override for custom validation. Raise ValidationError
        for verbose error messages.
        """
        if self.payments.exclude(status=ps.FAILED).exists():
            raise forms.ValidationError(
                _('Non-failed Payments exist for this Order.')
            )
        return True

    def get_items(self) -> list[ItemInfo]:
        """Return list of items for the payment."""
        return [
            {
                'name': self.get_description(),
                'quantity': 1,
                'unit_price': self.get_total_amount(),
            }
        ]

    def get_total_amount(self) -> Decimal:
        raise NotImplementedError

    def get_buyer_info(self) -> BuyerInfo:
        raise NotImplementedError

    def get_description(self) -> str:
        raise NotImplementedError


class AbstractPayment(models.Model):
    """Abstract payment model.

    FSM transitions are NOT defined on the model. Instead, use
    getpaid_core.fsm.create_payment_machine(payment) to attach
    transition triggers at runtime.
    """

    id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )
    order = models.ForeignKey(
        swapper.get_model_name('getpaid', 'Order'),
        verbose_name=_('order'),
        on_delete=models.CASCADE,
        related_name='payments',
    )
    amount_required = models.DecimalField(
        _('amount required'),
        decimal_places=2,
        max_digits=20,
        help_text=_(
            'Amount required to fulfill the payment; '
            'in selected currency, normal notation'
        ),
    )
    currency = models.CharField(_('currency'), max_length=3)
    status = models.CharField(
        _('status'),
        max_length=50,
        choices=ps.choices,
        default=ps.NEW,
        db_index=True,
    )
    backend = models.CharField(
        _('backend'), max_length=100, db_index=True
    )
    created_on = models.DateTimeField(
        _('created on'), auto_now_add=True, db_index=True
    )
    last_payment_on = models.DateTimeField(
        _('paid on'), blank=True, null=True, default=None, db_index=True
    )
    amount_locked = models.DecimalField(
        _('amount locked'),
        decimal_places=2,
        max_digits=20,
        default=0,
        help_text=_('Amount locked with this payment, ready to charge.'),
    )
    amount_paid = models.DecimalField(
        _('amount paid'),
        decimal_places=2,
        max_digits=20,
        default=0,
        help_text=_('Amount actually paid.'),
    )
    refunded_on = models.DateTimeField(
        _('refunded on'),
        blank=True,
        null=True,
        default=None,
        db_index=True,
    )
    amount_refunded = models.DecimalField(
        _('amount refunded'),
        decimal_places=2,
        max_digits=20,
        default=0,
    )
    external_id = models.CharField(
        _('external id'),
        max_length=64,
        blank=True,
        db_index=True,
        default='',
    )
    description = models.CharField(
        _('description'), max_length=128, blank=True, default=''
    )
    fraud_status = models.CharField(
        _('fraud status'),
        max_length=20,
        choices=fs.choices,
        default=fs.UNKNOWN,
        db_index=True,
    )
    fraud_message = models.TextField(_('fraud message'), blank=True)

    class Meta:
        abstract = True
        ordering = ['-created_on']
        verbose_name = _('Payment')
        verbose_name_plural = _('Payments')

    def __str__(self):
        return f'Payment #{self.id}'

    # ---- Properties ----

    @property
    def fully_paid(self) -> bool:
        return self.amount_paid >= self.amount_required

    def is_fully_paid(self) -> bool:
        """Check if payment is fully paid. Used by core FSM guard."""
        return self.amount_paid >= self.amount_required

    def is_fully_refunded(self) -> bool:
        """Check if payment is fully refunded. Used by core FSM guard."""
        return (
            self.amount_refunded > 0
            and self.amount_refunded >= self.amount_paid
        )

    # ---- Delegation helpers ----

    def get_unique_id(self) -> str:
        """Return unique identifier for this payment."""
        return str(self.id)

    def get_items(self) -> list[ItemInfo]:
        """Relay to order's get_items()."""
        return self.order.get_items()

    def get_buyer_info(self) -> BuyerInfo:
        return self.order.get_buyer_info()

    def get_return_redirect_url(
        self, request: HttpRequest, success: bool
    ) -> str:
        """Determine redirect URL after payment."""
        from getpaid.processor import BaseProcessor

        # Try to get processor for settings lookup
        try:
            processor = self._get_processor()
            if success:
                url = processor.get_setting('SUCCESS_URL')
            else:
                url = processor.get_setting('FAILURE_URL')
            if url is not None:
                kwargs = self.get_return_redirect_kwargs(request, success)
                return resolve_url(url, **kwargs)
        except (KeyError, GetPaidException):
            pass

        return resolve_url(
            self.order.get_return_url(self, success=success)
        )

    def get_return_redirect_kwargs(
        self, request: HttpRequest, success: bool
    ) -> dict:
        return {'pk': self.id}

    def _get_processor(self):
        """Get processor instance for this payment's backend."""
        from getpaid.registry import registry

        processor_class = registry[self.backend]
        return processor_class(self)
```

**Step 4: Run tests**

```bash
PYTHONPATH=.:example DJANGO_SETTINGS_MODULE=tests.settings python -m pytest tests/test_model_v3.py -v
```

Expected: ALL PASS

**Step 5: Commit**

```bash
git add getpaid/abstracts.py tests/test_model_v3.py
git commit --no-verify -m "refactor: rewrite AbstractPayment without django-fsm"
```

---

### Task 6: Add migration for FSMField -> CharField

**Files:**
- Create: `getpaid/migrations/0003_remove_fsm_fields.py`

**Step 1: Write the migration**

Since `FSMField` is a `CharField` subclass, the DB column is already varchar. This migration just updates Django's internal field tracking.

```python
"""Replace FSMField with CharField.

FSMField is a CharField subclass, so the database column is already
a varchar. This migration updates Django's field tracking only --
no actual database changes occur.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('getpaid', '0002_auto_20200417_2107'),
    ]

    operations = [
        migrations.AlterField(
            model_name='payment',
            name='status',
            field=models.CharField(
                choices=[
                    ('new', 'new'),
                    ('prepared', 'in progress'),
                    ('pre-auth', 'pre-authed'),
                    ('charge_started', 'charge process started'),
                    ('partially_paid', 'partially paid'),
                    ('paid', 'paid'),
                    ('failed', 'failed'),
                    ('refund_started', 'refund started'),
                    ('refunded', 'refunded'),
                ],
                db_index=True,
                default='new',
                max_length=50,
                verbose_name='status',
            ),
        ),
        migrations.AlterField(
            model_name='payment',
            name='fraud_status',
            field=models.CharField(
                choices=[
                    ('unknown', 'unknown'),
                    ('accepted', 'accepted'),
                    ('rejected', 'rejected'),
                    ('check', 'needs manual verification'),
                ],
                db_index=True,
                default='unknown',
                max_length=20,
                verbose_name='fraud status',
            ),
        ),
    ]
```

**Step 2: Verify migration applies**

```bash
PYTHONPATH=.:example DJANGO_SETTINGS_MODULE=tests.settings python -m django migrate --run-syncdb 2>&1 || true
```

**Step 3: Commit**

```bash
git add getpaid/migrations/0003_remove_fsm_fields.py
git commit --no-verify -m "feat: add migration to replace FSMField with CharField"
```

---

### Task 7: Rewrite dummy backend processor

Replace v2's dummy processor (which uses `django_fsm.can_proceed` and calls FSM methods directly on the payment) with one that uses getpaid-core's FSM.

**Files:**
- Modify: `getpaid/backends/dummy/processor.py`
- Modify: `getpaid/backends/dummy/apps.py`

**Step 1: Write tests for the v3 dummy processor**

Create `tests/test_dummy_v3.py`:

```python
"""Tests for the v3 dummy backend processor."""

import json
from decimal import Decimal

import pytest
import swapper

from getpaid.types import PaymentStatus as ps
from getpaid_core.fsm import create_payment_machine

pytestmark = pytest.mark.django_db

Order = swapper.load_model('getpaid', 'Order')
Payment = swapper.load_model('getpaid', 'Payment')


def _make_payment(**kwargs):
    order = Order.objects.create()
    defaults = {
        'order': order,
        'currency': order.currency,
        'amount_required': Decimal(str(order.get_total_amount())),
        'backend': 'getpaid.backends.dummy',
        'description': order.get_description(),
    }
    defaults.update(kwargs)
    return Payment.objects.create(**defaults)


class TestDummyV3Attributes:
    def test_slug(self):
        from getpaid.backends.dummy.processor import PaymentProcessor

        assert PaymentProcessor.slug == 'dummy'

    def test_inherits_django_base_processor(self):
        from getpaid.backends.dummy.processor import PaymentProcessor
        from getpaid.processor import BaseProcessor

        assert issubclass(PaymentProcessor, BaseProcessor)


class TestDummyV3PrepareTransaction:
    def test_rest_returns_redirect(self, rf, settings):
        settings.GETPAID_BACKEND_SETTINGS = {
            'getpaid.backends.dummy': {'paywall_method': 'REST'}
        }
        payment = _make_payment()
        proc = payment._get_processor()
        request = rf.get('/')

        # Attach FSM and prepare
        create_payment_machine(payment)
        result = proc.prepare_transaction(request=request)
        assert result.status_code == 302

    def test_post_returns_template(self, rf, settings):
        settings.GETPAID_BACKEND_SETTINGS = {
            'getpaid.backends.dummy': {'paywall_method': 'POST'}
        }
        payment = _make_payment()
        proc = payment._get_processor()
        request = rf.get('/')

        create_payment_machine(payment)
        result = proc.prepare_transaction(request=request)
        assert result.status_code == 200


class TestDummyV3HandleCallback:
    def test_callback_paid(self, rf):
        payment = _make_payment()
        create_payment_machine(payment)
        payment.confirm_prepared()
        payment.save()

        proc = payment._get_processor()
        request = rf.post(
            '',
            content_type='application/json',
            data={'new_status': ps.PAID},
        )
        response = proc.handle_paywall_callback(request)
        assert response.status_code == 200
        assert payment.status == ps.PAID

    def test_callback_failed(self, rf):
        payment = _make_payment()
        create_payment_machine(payment)
        payment.confirm_prepared()
        payment.save()

        proc = payment._get_processor()
        request = rf.post(
            '',
            content_type='application/json',
            data={'new_status': ps.FAILED},
        )
        response = proc.handle_paywall_callback(request)
        assert response.status_code == 200
        assert payment.status == ps.FAILED


class TestDummyV3FetchPaymentStatus:
    def test_new_no_callback(self):
        payment = _make_payment()
        proc = payment._get_processor()
        result = proc.fetch_payment_status()
        assert result.get('callback') is None

    def test_prepared_returns_confirm_payment(self):
        payment = _make_payment()
        create_payment_machine(payment)
        payment.confirm_prepared()
        payment.save()

        proc = payment._get_processor()
        result = proc.fetch_payment_status()
        assert result.get('callback') == 'confirm_payment'


class TestDummyV3Charge:
    def test_charge_returns_dict(self):
        payment = _make_payment()
        create_payment_machine(payment)
        payment.confirm_lock(amount=Decimal('100.00'))
        payment.save()

        proc = payment._get_processor()
        result = proc.charge(amount=Decimal('50.00'))
        assert result['amount_charged'] == Decimal('50.00')
        assert result['success'] is True
```

**Step 2: Run test to verify it fails**

```bash
PYTHONPATH=.:example DJANGO_SETTINGS_MODULE=tests.settings python -m pytest tests/test_dummy_v3.py -v
```

Expected: FAIL — dummy processor still imports from django_fsm.

**Step 3: Rewrite getpaid/backends/dummy/processor.py**

```python
"""Dummy payment backend for development and testing.

Self-contained processor simulating payment flows without external
HTTP calls. Supports REST/POST/GET initiation and PUSH/PULL confirmation.

Settings (via GETPAID_BACKEND_SETTINGS['getpaid.backends.dummy']):
    paywall_method: 'REST' | 'POST' | 'GET' (default: 'REST')
    confirmation_method: 'PUSH' | 'PULL' (default: 'PUSH')
"""

import json
import logging
from decimal import Decimal

from django.http import (
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseRedirect,
)
from django.template.response import TemplateResponse
from transitions.core import MachineError

from getpaid.post_forms import PaymentHiddenInputsPostForm
from getpaid.processor import BaseProcessor
from getpaid.types import PaymentStatus as ps
from getpaid_core.fsm import create_payment_machine

logger = logging.getLogger(__name__)


def _can_trigger(payment, trigger_name):
    """Check if a trigger can proceed without actually firing it."""
    trigger = getattr(payment, trigger_name, None)
    if trigger is None:
        return False
    try:
        return payment.may_trigger(trigger_name)
    except (AttributeError, MachineError):
        # If machine not attached or method unavailable
        return False


class PaymentProcessor(BaseProcessor):
    slug = 'dummy'
    display_name = 'Dummy'
    accepted_currencies = ['PLN', 'EUR']
    ok_statuses = [200]
    method = 'REST'
    confirmation_method = 'PUSH'
    post_form_class = PaymentHiddenInputsPostForm
    post_template_name = 'getpaid_dummy/payment_post_form.html'

    def get_paywall_method(self):
        return self.get_setting('paywall_method', self.method)

    def get_confirmation_method(self):
        return self.get_setting(
            'confirmation_method', self.confirmation_method
        ).upper()

    def prepare_transaction(self, request=None, view=None, **kwargs):
        """Simulate payment preparation. No external HTTP calls."""
        method = self.get_paywall_method()

        # Ensure FSM is attached
        create_payment_machine(self.payment)
        self.payment.confirm_prepared()
        self.payment.save()

        if method == 'POST':
            params = {
                'amount': str(self.payment.amount_required),
                'currency': self.payment.currency,
                'description': self.payment.description,
            }
            form = self.get_form(params)
            return TemplateResponse(
                request=request,
                template=self.get_template_names(view=view),
                context={'form': form, 'paywall_url': '#dummy'},
            )

        redirect_url = self.get_our_baseurl(request)
        return HttpResponseRedirect(redirect_url)

    def handle_paywall_callback(self, request, **kwargs):
        """Handle a simulated callback with JSON body."""
        try:
            data = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return HttpResponseBadRequest('Invalid JSON')

        new_status = data.get('new_status')
        if new_status is None:
            return HttpResponseBadRequest('Missing new_status')

        create_payment_machine(self.payment)

        if new_status == ps.FAILED:
            self.payment.fail()
        elif new_status == ps.PRE_AUTH:
            self.payment.confirm_lock()
        elif new_status == ps.PAID:
            if _can_trigger(self.payment, 'confirm_lock'):
                self.payment.confirm_lock()
            if _can_trigger(self.payment, 'confirm_payment'):
                self.payment.confirm_payment()
            if _can_trigger(self.payment, 'mark_as_paid'):
                try:
                    self.payment.mark_as_paid()
                except MachineError:
                    logger.debug(
                        'Cannot mark as paid (guard failed).',
                        extra={'payment_id': self.payment.id},
                    )
        else:
            return HttpResponseBadRequest(
                f'Unhandled status: {new_status}'
            )

        self.payment.save()
        return HttpResponse('OK')

    def fetch_payment_status(self, **kwargs):
        """Simulate fetching status from external provider."""
        status = self.payment.status
        simulated = self.get_setting('confirmation_status', 'paid')

        if status in (
            ps.PAID,
            ps.FAILED,
            ps.REFUNDED,
            ps.REFUND_STARTED,
        ):
            return {}

        if status == ps.NEW:
            return {}

        if simulated == 'failed':
            return {'callback': 'fail'}
        elif simulated == 'pre_auth':
            return {'callback': 'confirm_lock'}
        else:
            return {
                'callback': 'confirm_payment',
                'amount': self.payment.amount_required,
            }

    def charge(self, amount=None, **kwargs):
        """Simulate charging a pre-authorized amount."""
        if amount is None:
            amount = self.payment.amount_locked
        return {
            'amount_charged': Decimal(str(amount)),
            'success': True,
        }

    def release_lock(self, **kwargs):
        """Simulate releasing a locked amount."""
        return Decimal(str(self.payment.amount_locked))

    def start_refund(self, amount=None, **kwargs):
        """Simulate starting a refund."""
        if amount is None:
            amount = self.payment.amount_paid
        return Decimal(str(amount))

    def cancel_refund(self, **kwargs):
        """Simulate cancelling a refund."""
        return True
```

**Step 4: Update getpaid/backends/dummy/apps.py**

```python
from django.apps import AppConfig
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.translation import gettext_lazy as _


class DummyPluginAppConfig(AppConfig):
    name = 'getpaid.backends.dummy'
    label = 'getpaid_dummy'
    verbose_name = _('Dummy paywall')
    default_auto_field = 'django.db.models.AutoField'

    def ready(self):
        if not settings.DEBUG:
            raise ImproperlyConfigured(
                'Do not use dummy plugin on production!'
            )

        from getpaid.registry import registry

        registry.register(self.module)
```

**Step 5: Run tests**

```bash
PYTHONPATH=.:example DJANGO_SETTINGS_MODULE=tests.settings python -m pytest tests/test_dummy_v3.py -v
```

Expected: ALL PASS

**Step 6: Commit**

```bash
git add getpaid/backends/dummy/processor.py getpaid/backends/dummy/apps.py tests/test_dummy_v3.py
git commit --no-verify -m "refactor: rewrite dummy backend without django-fsm"
```

---

### Task 8: Update views

Views need minimal changes. The main change is that `CreatePaymentView.form_valid()` needs to attach FSM before calling `prepare_transaction`, and `CallbackDetailView` needs to use the new processor API.

**Files:**
- Modify: `getpaid/views.py`

**Step 1: Write tests for updated views**

Create `tests/test_views_v3.py`:

```python
"""Tests for django-getpaid v3 views."""

import json
from decimal import Decimal

import pytest
import swapper
from django.test import RequestFactory

from getpaid.types import PaymentStatus as ps
from getpaid.views import (
    CallbackDetailView,
    CreatePaymentView,
    SuccessView,
    FailureView,
)

pytestmark = pytest.mark.django_db

Order = swapper.load_model('getpaid', 'Order')
Payment = swapper.load_model('getpaid', 'Payment')


class TestCallbackDetailView:
    def test_post_delegates_to_processor(self, rf, settings):
        settings.GETPAID_BACKEND_SETTINGS = {
            'getpaid.backends.dummy': {
                'paywall_method': 'REST',
                'confirmation_method': 'PUSH',
            }
        }
        order = Order.objects.create()
        payment = Payment.objects.create(
            order=order,
            amount_required=order.get_total_amount(),
            currency=order.currency,
            backend='getpaid.backends.dummy',
            description=order.get_description(),
        )
        # Move to PREPARED so callback can work
        from getpaid_core.fsm import create_payment_machine

        create_payment_machine(payment)
        payment.confirm_prepared()
        payment.save()

        request = rf.post(
            f'/payments/callback/{payment.pk}/',
            content_type='application/json',
            data={'new_status': ps.PAID},
        )
        view = CallbackDetailView()
        response = view.post(request, pk=payment.pk)
        assert response.status_code == 200


class TestFallbackViews:
    def test_success_view_redirects(self, rf, settings):
        settings.DEBUG = True
        order = Order.objects.create()
        payment = Payment.objects.create(
            order=order,
            amount_required=order.get_total_amount(),
            currency=order.currency,
            backend='getpaid.backends.dummy',
            description=order.get_description(),
        )
        request = rf.get(f'/payments/success/{payment.pk}/')
        view = SuccessView()
        view.kwargs = {'pk': payment.pk}
        view.request = request
        url = view.get_redirect_url(pk=payment.pk)
        assert url is not None
```

**Step 2: Rewrite getpaid/views.py**

```python
"""Payment views for django-getpaid v3."""

import logging

import swapper
from django import http
from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import CreateView, RedirectView

from .exceptions import GetPaidException
from .forms import PaymentMethodForm

logger = logging.getLogger(__name__)


class CreatePaymentView(CreateView):
    model = swapper.load_model('getpaid', 'Payment')
    form_class = PaymentMethodForm

    def get(self, request, *args, **kwargs):
        return http.HttpResponseNotAllowed(['POST'])

    def form_valid(self, form):
        payment = form.save()
        return payment._get_processor().prepare_transaction(
            request=self.request, view=self
        )

    def form_invalid(self, form):
        return super().form_invalid(form)


new_payment = CreatePaymentView.as_view()


class FallbackView(RedirectView):
    """Return view from paywall after payment completion/rejection."""

    success = None
    permanent = False

    def get_redirect_url(self, *args, **kwargs):
        Payment = swapper.load_model('getpaid', 'Payment')
        payment = get_object_or_404(Payment, pk=self.kwargs['pk'])
        return payment.get_return_redirect_url(
            request=self.request, success=self.success
        )


class SuccessView(FallbackView):
    success = True


success = SuccessView.as_view()


class FailureView(FallbackView):
    success = False


failure = FailureView.as_view()


class CallbackDetailView(View):
    """Handle paywall callback via PUSH flow."""

    def post(self, request: HttpRequest, pk, *args, **kwargs):
        Payment = swapper.load_model('getpaid', 'Payment')
        payment = get_object_or_404(Payment, pk=pk)
        processor = payment._get_processor()
        try:
            processor.verify_callback_request(request)
        except GetPaidException:
            logger.warning(
                'Callback verification failed for payment %s', pk
            )
            return http.HttpResponseForbidden(
                'Callback verification failed'
            )
        return processor.handle_paywall_callback(request, *args, **kwargs)


callback = csrf_exempt(CallbackDetailView.as_view())
```

**Step 3: Run tests**

```bash
PYTHONPATH=.:example DJANGO_SETTINGS_MODULE=tests.settings python -m pytest tests/test_views_v3.py -v
```

Expected: ALL PASS

**Step 4: Commit**

```bash
git add getpaid/views.py tests/test_views_v3.py
git commit --no-verify -m "refactor: update views for v3 (no direct processor property)"
```

---

### Task 9: Update example app signals

The example app's `signals.py` imports from `django_fsm.signals` which no longer exists. Replace with Django's `post_save`.

**Files:**
- Modify: `example/orders/signals.py`

**Step 1: Rewrite example/orders/signals.py**

```python
import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from getpaid import PaymentStatus

logger = logging.getLogger('getpaid_example')


@receiver(post_save)
def payment_status_changed_listener(sender, instance, **kwargs):
    """Update order status when payment is completed."""
    # Only act on Payment models
    if not hasattr(instance, 'order') or not hasattr(instance, 'status'):
        return

    from getpaid.abstracts import AbstractPayment

    if not isinstance(instance, AbstractPayment):
        return

    if instance.status == PaymentStatus.PAID:
        logger.debug(
            'Payment %s is PAID, updating order status.',
            instance.id,
        )
        instance.order.status = 'P'
        instance.order.save()
```

**Step 2: Commit**

```bash
git add example/orders/signals.py
git commit --no-verify -m "fix: replace django_fsm.signals with Django post_save in example app"
```

---

### Task 10: Update test settings and remove django-fsm imports

Remove `django-fsm` from all imports across the test suite. Update existing tests that reference `django_fsm.can_proceed` or `from django_fsm import`.

**Files:**
- Modify: `tests/test_fsm.py` (full rewrite)
- Modify: `tests/test_integration.py` (remove django_fsm imports)
- Modify: `tests/test_abstracts.py` (update for new model API)
- Modify: `tests/test_processor.py` (update for new processor API)
- Modify: `tests/test_dummy_backend.py` (update for FSM attachment)
- Modify: `tests/test_deprecated_cleanup.py` (remove FSMField checks)
- Modify: `tests/test_registry.py` (update for new registry)

**Step 1: Rewrite tests/test_fsm.py**

Replace `from django_fsm import can_proceed` with transitions-based checks:

```python
"""FSM transition tests using getpaid-core's transitions library."""

import pytest
import swapper

from getpaid.status import PaymentStatus as ps
from getpaid_core.fsm import create_payment_machine
from transitions.core import MachineError

dummy = 'getpaid.backends.dummy'

Order = swapper.load_model('getpaid', 'Order')
Payment = swapper.load_model('getpaid', 'Payment')

pytestmark = pytest.mark.django_db


def _can_trigger(payment, name):
    """Check if trigger can fire without actually firing."""
    try:
        return payment.may_trigger(name)
    except AttributeError:
        return False


def test_fsm_direct_prepare(payment_factory):
    payment = payment_factory()
    create_payment_machine(payment)
    assert payment.status == ps.NEW
    payment.confirm_prepared()
    assert payment.status == ps.PREPARED


def test_fsm_check_available_transitions_from_new(payment_factory):
    payment = payment_factory()
    create_payment_machine(payment)
    assert payment.status == ps.NEW

    assert _can_trigger(payment, 'confirm_prepared')
    assert _can_trigger(payment, 'confirm_lock')
    assert not _can_trigger(payment, 'confirm_charge_sent')
    assert not _can_trigger(payment, 'confirm_payment')
    assert not _can_trigger(payment, 'mark_as_paid')
    assert not _can_trigger(payment, 'release_lock')
    assert not _can_trigger(payment, 'start_refund')
    assert not _can_trigger(payment, 'cancel_refund')
    assert not _can_trigger(payment, 'confirm_refund')
    assert not _can_trigger(payment, 'mark_as_refunded')
    assert _can_trigger(payment, 'fail')


def test_fsm_check_available_transitions_from_failed(payment_factory):
    payment = payment_factory()
    create_payment_machine(payment)
    payment.fail()
    assert payment.status == ps.FAILED

    assert not _can_trigger(payment, 'confirm_prepared')
    assert not _can_trigger(payment, 'confirm_lock')
    assert not _can_trigger(payment, 'confirm_charge_sent')
    assert not _can_trigger(payment, 'confirm_payment')
    assert not _can_trigger(payment, 'mark_as_paid')
    assert not _can_trigger(payment, 'release_lock')
    assert not _can_trigger(payment, 'start_refund')
    assert not _can_trigger(payment, 'cancel_refund')
    assert not _can_trigger(payment, 'confirm_refund')
    assert not _can_trigger(payment, 'mark_as_refunded')
    assert not _can_trigger(payment, 'fail')


def test_fsm_check_available_transitions_from_prepared(payment_factory):
    payment = payment_factory()
    create_payment_machine(payment)
    payment.confirm_prepared()
    assert payment.status == ps.PREPARED

    assert not _can_trigger(payment, 'confirm_prepared')
    assert _can_trigger(payment, 'confirm_lock')
    assert not _can_trigger(payment, 'confirm_charge_sent')
    assert _can_trigger(payment, 'confirm_payment')
    assert not _can_trigger(payment, 'mark_as_paid')
    assert not _can_trigger(payment, 'release_lock')
    assert not _can_trigger(payment, 'start_refund')
    assert not _can_trigger(payment, 'cancel_refund')
    assert not _can_trigger(payment, 'confirm_refund')
    assert not _can_trigger(payment, 'mark_as_refunded')
    assert _can_trigger(payment, 'fail')


def test_fsm_check_available_transitions_from_locked(payment_factory):
    payment = payment_factory()
    create_payment_machine(payment)
    payment.confirm_lock()
    assert payment.status == ps.PRE_AUTH

    assert not _can_trigger(payment, 'confirm_prepared')
    assert not _can_trigger(payment, 'confirm_lock')
    assert _can_trigger(payment, 'confirm_charge_sent')
    assert _can_trigger(payment, 'confirm_payment')
    assert not _can_trigger(payment, 'mark_as_paid')
    assert _can_trigger(payment, 'release_lock')
    assert not _can_trigger(payment, 'start_refund')
    assert not _can_trigger(payment, 'cancel_refund')
    assert not _can_trigger(payment, 'confirm_refund')
    assert not _can_trigger(payment, 'mark_as_refunded')
    assert _can_trigger(payment, 'fail')


def test_fsm_check_available_transitions_from_partial(payment_factory):
    payment = payment_factory()
    create_payment_machine(payment)
    payment.confirm_lock()
    payment.confirm_payment()
    assert payment.status == ps.PARTIAL

    assert not _can_trigger(payment, 'confirm_prepared')
    assert not _can_trigger(payment, 'confirm_lock')
    assert not _can_trigger(payment, 'confirm_charge_sent')
    assert _can_trigger(payment, 'confirm_payment')
    # mark_as_paid has a guard -- may_trigger may return True
    # but actual trigger will raise MachineError if not fully paid
    assert _can_trigger(payment, 'mark_as_paid')
    assert not _can_trigger(payment, 'release_lock')
    assert _can_trigger(payment, 'start_refund')
    assert not _can_trigger(payment, 'cancel_refund')
    assert not _can_trigger(payment, 'confirm_refund')
    assert not _can_trigger(payment, 'fail')
    assert _can_trigger(payment, 'mark_as_refunded')


def test_fsm_check_available_transitions_from_paid(payment_factory):
    payment = payment_factory()
    create_payment_machine(payment)
    payment.confirm_lock()
    payment.confirm_payment()
    # Need to set amount_paid for guard
    payment.amount_paid = payment.amount_required
    payment.mark_as_paid()
    assert payment.status == ps.PAID

    assert not _can_trigger(payment, 'confirm_prepared')
    assert not _can_trigger(payment, 'confirm_lock')
    assert not _can_trigger(payment, 'confirm_charge_sent')
    assert not _can_trigger(payment, 'confirm_payment')
    assert not _can_trigger(payment, 'mark_as_paid')
    assert not _can_trigger(payment, 'release_lock')
    assert _can_trigger(payment, 'start_refund')
    assert not _can_trigger(payment, 'cancel_refund')
    assert not _can_trigger(payment, 'confirm_refund')
    assert not _can_trigger(payment, 'mark_as_refunded')
    assert not _can_trigger(payment, 'fail')
```

**Step 2: Update tests/test_integration.py**

Remove `from django_fsm import can_proceed` and use `_can_trigger` helper or direct state checks. Update transition calls to attach FSM first.

Key changes:
- Remove `from django_fsm import can_proceed`
- Add `from getpaid_core.fsm import create_payment_machine`
- Before any transition call on payment, call `create_payment_machine(payment)`
- Replace `can_proceed(payment.mark_as_paid)` with `payment.may_trigger('mark_as_paid')`

**Step 3: Update tests/test_abstracts.py**

Key changes:
- Remove `_processor` property tests (removed from model)
- Update FSM tests to use `create_payment_machine(payment)` before transitions
- Remove `TransitionNotAllowed` references
- Update `fetch_and_update_status` tests (this method is removed from model — test must be updated or removed)
- Keep field precision, verbose name, and validator tests as-is

**Step 4: Update tests/test_processor.py**

Key changes:
- `CallbackDetailView` now calls `verify_callback_request()` instead of `verify_callback()`
- Update mock setup accordingly

**Step 5: Update tests/test_dummy_backend.py**

Key changes:
- Add `create_payment_machine(payment)` before any FSM transitions
- Remove `from django_fsm import can_proceed`

**Step 6: Update tests/test_deprecated_cleanup.py**

Key changes:
- Remove any references to FSMField
- Update `test_pyproject_declares_django_dependency` if needed

**Step 7: Update tests/test_registry.py**

Key changes:
- Tests should use the new `DjangoPluginRegistry` API
- `registry.get_all_supported_currency_choices()` API is the same

**Step 8: Run full test suite**

```bash
PYTHONPATH=.:example DJANGO_SETTINGS_MODULE=tests.settings python -m pytest tests/ -v
```

Expected: ALL PASS (or identify remaining failures).

**Step 9: Commit**

```bash
git add tests/
git commit --no-verify -m "test: rewrite all tests for v3 (no django-fsm)"
```

---

### Task 11: Final cleanup and lint

**Files:**
- Various

**Step 1: Verify no django-fsm imports remain**

```bash
grep -r "django_fsm" getpaid/ tests/ example/ --include="*.py" || echo "CLEAN"
```

Expected: "CLEAN" (no matches).

**Step 2: Run ruff lint**

```bash
ruff check getpaid/ tests/ --fix
```

**Step 3: Run ruff format**

```bash
ruff format getpaid/ tests/
```

**Step 4: Run full test suite**

```bash
PYTHONPATH=.:example DJANGO_SETTINGS_MODULE=tests.settings python -m pytest tests/ -v --tb=short
```

Expected: ALL PASS.

**Step 5: Run with coverage**

```bash
PYTHONPATH=.:example DJANGO_SETTINGS_MODULE=tests.settings python -m pytest tests/ --cov=getpaid --cov-report=term-missing
```

**Step 6: Commit**

```bash
git add -A
git commit --no-verify -m "chore: final cleanup, lint, format for v3"
```

---

### Task 12: Verify and tag

**Step 1: Full verification**

```bash
PYTHONPATH=.:example DJANGO_SETTINGS_MODULE=tests.settings python -m pytest tests/ -v --tb=short
```

Expected: ALL PASS.

**Step 2: Verify version**

```bash
python -c "import getpaid; print(getpaid.__version__)"
```

Expected: `3.0.0a1`

**Step 3: Verify no django-fsm dependency**

```bash
python -c "import django_fsm" 2>&1 | grep -q "ModuleNotFoundError" && echo "GOOD: django-fsm not installed"
```

**Step 4: Commit final state and prepare for review**

No tag yet — this goes through code review first via `superpowers:finishing-a-development-branch`.

---

## Summary

| Task | Description | Key files |
|------|-------------|-----------|
| 1 | Create branch, update pyproject.toml | `pyproject.toml` |
| 2 | Re-export enums, types, exceptions from core | `getpaid/types.py`, `getpaid/exceptions.py`, `getpaid/__init__.py` |
| 3 | Replace registry with core adapter | `getpaid/registry.py` |
| 4 | Rewrite BaseProcessor as Django adapter | `getpaid/processor.py` |
| 5 | Rewrite AbstractPayment model | `getpaid/abstracts.py` |
| 6 | Add FSMField->CharField migration | `getpaid/migrations/0003_*.py` |
| 7 | Rewrite dummy backend | `getpaid/backends/dummy/processor.py` |
| 8 | Update views | `getpaid/views.py` |
| 9 | Update example app signals | `example/orders/signals.py` |
| 10 | Rewrite all tests | `tests/*.py` |
| 11 | Final cleanup and lint | Various |
| 12 | Verify and prepare for review | N/A |
