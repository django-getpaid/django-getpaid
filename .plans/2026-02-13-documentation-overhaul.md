# Documentation Overhaul Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Overhaul documentation for both getpaid-core and django-getpaid — convert to Markdown (MyST), update all outdated references, write migration guide, add proper API reference via autodoc, and update ReadTheDocs configs.

**Architecture:** Both projects use Sphinx with MyST parser (Markdown) and furo theme. Documentation lives in `docs/` directories. Root-level README.md files serve as PyPI landing pages and are included in Sphinx docs via MyST `{include}`. Internal plan documents move from `docs/plans/` to `.plans/` to keep them out of Sphinx builds.

**Tech Stack:** Sphinx 8+, MyST Parser 4+, furo theme, autodoc + napoleon + autosummary extensions, ReadTheDocs hosting

**Branch:** `docs/overhaul` (from `master`)

**IMPORTANT NOTES:**
- Commit with `--no-verify` (pre-commit hook not in PATH)
- getpaid-core is at `../getpaid-core/`, django-getpaid is at `../django-getpaid/`
- Both projects use `uv` for dependency management
- No TDD for docs — verify with `uv run sphinx-build -W docs docs/_build` instead
- Tasks 1-5 are for getpaid-core, Tasks 6-14 are for django-getpaid

---

### Task 1: Move internal plan docs out of docs/ (both projects)

**Files:**
- Move: `docs/plans/` → `.plans/` (both projects)

**Step 1: Move plans in django-getpaid**

```bash
cd /home/minder/projekty/django-getpaid/django-getpaid
mkdir -p .plans
git mv docs/plans/2026-02-13-django-getpaid-v3-design.md .plans/
git mv docs/plans/2026-02-13-django-getpaid-v3-implementation.md .plans/
git mv docs/plans/2026-02-13-documentation-overhaul.md .plans/
rmdir docs/plans
```

**Step 2: Move plans in getpaid-core**

```bash
cd /home/minder/projekty/django-getpaid/getpaid-core
mkdir -p .plans
git mv docs/plans/2026-02-13-getpaid-core-design.md .plans/
git mv docs/plans/2026-02-13-getpaid-core-implementation.md .plans/
rmdir docs/plans
```

**Step 3: Commit**

```bash
# In django-getpaid:
git add -A && git commit --no-verify -m "chore: move internal plan docs from docs/plans/ to .plans/"
# In getpaid-core:
git add -A && git commit --no-verify -m "chore: move internal plan docs from docs/plans/ to .plans/"
```

---

### Task 2: Update getpaid-core Sphinx config and build deps

**Files:**
- Modify: `getpaid-core/docs/conf.py`
- Modify: `getpaid-core/docs/requirements.txt`
- Modify: `getpaid-core/.readthedocs.yml`

**Step 1: Rewrite docs/conf.py**

```python
"""Sphinx configuration for getpaid-core."""

project = "getpaid-core"
author = "Dominik Kozaczko"
copyright = "2022-2026, Dominik Kozaczko"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
    "sphinx.ext.intersphinx",
    "myst_parser",
]

autodoc_typehints = "description"
autodoc_member_order = "bysource"
autosummary_generate = True

html_theme = "furo"
html_title = "getpaid-core"

myst_enable_extensions = [
    "colon_fence",
    "fieldlist",
]

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
}
```

**Step 2: Update docs/requirements.txt**

```
furo>=2024.8.6
sphinx>=8.0
myst-parser>=4.0
```

**Step 3: Update .readthedocs.yml**

```yaml
version: 2
build:
  os: ubuntu-24.04
  tools:
    python: "3.12"
sphinx:
  configuration: docs/conf.py
formats: all
python:
  install:
    - requirements: docs/requirements.txt
    - path: .
```

**Step 4: Verify build**

```bash
cd /home/minder/projekty/django-getpaid/getpaid-core
uv run pip install -r docs/requirements.txt
uv run sphinx-build -W docs docs/_build
```

Expected: Build succeeds (warnings may appear for missing pages — that's OK at this stage).

**Step 5: Commit**

```bash
git add -A && git commit --no-verify -m "docs: update Sphinx config, deps, and RTD config for getpaid-core"
```

---

### Task 3: Rewrite getpaid-core README.md

**Files:**
- Modify: `getpaid-core/README.md`

**Step 1: Replace README.md with proper content**

```markdown
# getpaid-core

[![PyPI](https://img.shields.io/pypi/v/getpaid-core.svg)](https://pypi.org/project/getpaid-core/)
[![Python Version](https://img.shields.io/pypi/pyversions/getpaid-core)](https://pypi.org/project/getpaid-core/)
[![License](https://img.shields.io/pypi/l/getpaid-core)](https://github.com/django-getpaid/getpaid-core/blob/main/LICENSE)

Framework-agnostic payment processing library for Python. Provides the core
abstractions — enums, protocols, FSM, processor base class, plugin registry,
and exception hierarchy — that framework-specific adapters build on.

## Architecture

getpaid-core defines the **what** of payment processing without coupling to
any web framework:

- **Enums** (`PaymentStatus`, `FraudStatus`, `BackendMethod`, `ConfirmationMethod`)
  define all valid states and methods.
- **Protocols** (`Payment`, `Order`, `PaymentRepository`) define structural
  contracts that framework models must satisfy.
- **FSM** (`create_payment_machine`, `create_fraud_machine`) attaches
  state-machine triggers to payment objects at runtime using the `transitions`
  library.
- **BaseProcessor** is an abstract class that payment gateway plugins subclass
  to implement `prepare_transaction`, `handle_callback`, `charge`, etc.
- **PluginRegistry** discovers and stores payment backend processors via
  entry points or manual registration.
- **Exceptions** provide a structured hierarchy for payment errors.

## Framework Adapters

- **[django-getpaid](https://github.com/django-getpaid/django-getpaid)** —
  Django adapter (models, views, forms, admin)

## Installation

```bash
pip install getpaid-core
```

You typically install this as a dependency of a framework adapter rather than
directly.

## Quick Example

```python
from getpaid_core.enums import PaymentStatus
from getpaid_core.fsm import create_payment_machine

# Any object satisfying the Payment protocol works
payment = MyPayment(status=PaymentStatus.NEW, amount_required=100)
machine = create_payment_machine(payment)

# FSM trigger methods are attached directly to the object
payment.confirm_prepared()
assert payment.status == PaymentStatus.PREPARED
```

## Requirements

- Python 3.12+
- transitions
- httpx
- anyio

## License

MIT

## Credits

Created by [Dominik Kozaczko](https://github.com/dekoza).
```

**Step 2: Commit**

```bash
git add -A && git commit --no-verify -m "docs: rewrite getpaid-core README with proper content"
```

---

### Task 4: Write getpaid-core documentation pages

**Files:**
- Create: `getpaid-core/docs/getting-started.md`
- Create: `getpaid-core/docs/concepts.md`
- Create: `getpaid-core/docs/changelog.md`
- Modify: `getpaid-core/docs/reference.md`
- Modify: `getpaid-core/docs/index.md`
- Delete: `getpaid-core/docs/usage.md`

**Step 1: Create docs/getting-started.md**

```markdown
# Getting Started

## Installation

Install getpaid-core from PyPI:

```bash
pip install getpaid-core
```

Or add it as a dependency with uv:

```bash
uv add getpaid-core
```

## Basic Concepts

getpaid-core is a **library, not a framework**. It provides building blocks
that framework adapters (like django-getpaid) use to implement payment
processing. You typically don't use getpaid-core directly in application code
— instead, you use a framework adapter.

If you're building a **new framework adapter** or a **payment gateway plugin**,
read on.

## Creating a Payment Processor Plugin

Every payment gateway needs a processor — a class that knows how to talk to
that gateway's API. Subclass `BaseProcessor` and implement at least
`prepare_transaction`:

```python
from decimal import Decimal
from getpaid_core.processor import BaseProcessor
from getpaid_core.types import TransactionResult


class MyGatewayProcessor(BaseProcessor):
    slug = "my-gateway"
    display_name = "My Payment Gateway"
    accepted_currencies = ["USD", "EUR", "PLN"]
    sandbox_url = "https://sandbox.mygateway.com"
    production_url = "https://api.mygateway.com"

    async def prepare_transaction(self, **kwargs) -> TransactionResult:
        # Call your gateway's API to create a payment session
        api_key = self.get_setting("api_key")
        amount = self.payment.amount_required
        currency = self.payment.currency

        # ... call gateway API ...

        return TransactionResult(
            redirect_url="https://mygateway.com/pay/session123",
            form_data=None,
            method="GET",
            headers={},
        )
```

## Registering a Plugin

Plugins are discovered via Python entry points. Add this to your plugin's
`pyproject.toml`:

```toml
[project.entry-points."getpaid.backends"]
my-gateway = "my_gateway.processor:MyGatewayProcessor"
```

Or register manually for testing:

```python
from getpaid_core.registry import registry

registry.register(MyGatewayProcessor)
```

## Payment State Machine

Payments move through states via an FSM powered by the `transitions` library.
The machine attaches trigger methods directly to payment objects:

```python
from getpaid_core.fsm import create_payment_machine

machine = create_payment_machine(payment)

# Now payment has trigger methods:
payment.confirm_prepared()   # NEW -> PREPARED
payment.confirm_lock(amount=100)  # PREPARED -> PRE_AUTH
payment.confirm_payment(amount=100)  # PRE_AUTH -> PARTIAL
payment.mark_as_paid()       # PARTIAL -> PAID (if fully paid)
```

See {doc}`concepts` for the full state diagram and transition rules.
```

**Step 2: Create docs/concepts.md**

```markdown
# Core Concepts

## Payment Statuses

Payments move through these states:

| Status | Value | Description |
|--------|-------|-------------|
| `NEW` | `"new"` | Just created, not yet sent to gateway |
| `PREPARED` | `"prepared"` | Sent to gateway, waiting for buyer action |
| `PRE_AUTH` | `"pre-auth"` | Amount pre-authorized (locked) |
| `IN_CHARGE` | `"charge_started"` | Charge request sent for pre-authed payment |
| `PARTIAL` | `"partially_paid"` | Some amount received |
| `PAID` | `"paid"` | Fully paid |
| `FAILED` | `"failed"` | Payment failed |
| `REFUND_STARTED` | `"refund_started"` | Refund initiated |
| `REFUNDED` | `"refunded"` | Fully refunded or lock released |

## Payment State Transitions

```
NEW ──────────────────────► PREPARED
 │                             │
 │  confirm_lock               │ confirm_lock
 ▼                             ▼
PRE_AUTH ◄─────────────────────┘
 │
 ├── confirm_charge_sent ──► IN_CHARGE
 │                             │
 │   confirm_payment           │ confirm_payment
 ▼                             ▼
PARTIAL ◄──────────────────────┘
 │
 ├── mark_as_paid ──────────► PAID
 │
 ├── start_refund ──────────► REFUND_STARTED
 │                             │
 │   cancel_refund             │ confirm_refund
 ◄─────────────────────────────┘
 │
 └── mark_as_refunded ──────► REFUNDED

NEW/PREPARED/PRE_AUTH ──fail──► FAILED
PRE_AUTH ──release_lock──────► REFUNDED
```

### Transition Guards

Some transitions have guards that raise `MachineError` if conditions aren't met:

- **`mark_as_paid`** requires `is_fully_paid()` — `amount_paid >= amount_required`
- **`mark_as_refunded`** requires `is_fully_refunded()` — `amount_refunded >= amount_paid`

### Amount Callbacks

- **`confirm_lock`** stores the locked amount via `_store_locked_amount`
- **`confirm_payment`** accumulates paid amount via `_accumulate_paid_amount`

## Fraud Statuses

| Status | Value | Description |
|--------|-------|-------------|
| `UNKNOWN` | `"unknown"` | Not yet checked |
| `ACCEPTED` | `"accepted"` | Passed fraud check |
| `REJECTED` | `"rejected"` | Failed fraud check |
| `CHECK` | `"check"` | Needs manual review |

### Fraud Transitions

```
UNKNOWN ── flag_as_fraud ──► REJECTED
UNKNOWN ── flag_as_legit ──► ACCEPTED
UNKNOWN ── flag_for_check ─► CHECK
CHECK ──── mark_as_fraud ──► REJECTED
CHECK ──── mark_as_legit ──► ACCEPTED
```

## Protocols

getpaid-core uses Python protocols (structural subtyping) instead of base
classes for framework integration. Any object with the right attributes and
methods satisfies the protocol — no inheritance required.

### Order Protocol

```python
class Order(Protocol):
    def get_total_amount(self) -> Decimal: ...
    def get_buyer_info(self) -> BuyerInfo: ...
    def get_description(self) -> str: ...
    def get_currency(self) -> str: ...
    def get_items(self) -> list[ItemInfo]: ...
    def get_return_url(self, success: bool | None = None) -> str: ...
```

### Payment Protocol

```python
class Payment(Protocol):
    id: str
    order: Order
    amount_required: Decimal
    currency: str
    status: str
    backend: str
    external_id: str
    description: str
    amount_paid: Decimal
    amount_locked: Decimal
    amount_refunded: Decimal
    fraud_status: str
    fraud_message: str
```

### PaymentRepository Protocol

```python
class PaymentRepository(Protocol):
    async def get_by_id(self, payment_id: str) -> Payment: ...
    async def create(self, **kwargs) -> Payment: ...
    async def save(self, payment: Payment) -> Payment: ...
    async def update_status(self, payment_id: str, status: str, **fields) -> Payment: ...
    async def list_by_order(self, order_id: str) -> list[Payment]: ...
```

## Plugin Registry

The `PluginRegistry` discovers payment backend processors via Python entry
points (the `getpaid.backends` group) and provides lookup by slug or currency:

```python
from getpaid_core.registry import registry

# Auto-discovers on first use
backends = registry.get_for_currency("PLN")
choices = registry.get_choices("EUR")  # [(slug, display_name), ...]
processor_class = registry.get_by_slug("my-gateway")
```

## Exception Hierarchy

```
GetPaidException
├── CommunicationError
│   ├── ChargeFailure
│   ├── LockFailure
│   └── RefundFailure
├── CredentialsError
├── InvalidCallbackError
└── InvalidTransitionError
```

All exceptions accept an optional `context` dict for structured error info:

```python
raise ChargeFailure("Gateway returned 500", context={"status_code": 500})
```

## Type Definitions

| Type | Description |
|------|-------------|
| `BuyerInfo` | TypedDict with `email`, `first_name`, `last_name`, `phone` (all optional) |
| `ItemInfo` | TypedDict with `name`, `quantity`, `unit_price` |
| `ChargeResponse` | TypedDict with `amount_charged`, `success`, `async_call` |
| `PaymentStatusResponse` | TypedDict with `amount`, `status`, `external_id` (all optional) |
| `TransactionResult` | TypedDict with `redirect_url`, `form_data`, `method`, `headers` |
```

**Step 3: Create docs/changelog.md**

```markdown
# Changelog

## v0.1.0 (2026-02-13)

Initial release — extracted from django-getpaid v2 and redesigned as a
framework-agnostic library.

### Features

- Payment status enum (`PaymentStatus`) with 9 states matching django-getpaid v2
  values for backward compatibility
- Fraud status enum (`FraudStatus`) with 4 states
- Backend method and confirmation method enums
- `BaseProcessor` abstract class for payment gateway plugins
- Payment and fraud state machines using `transitions` library
- Transition guards (`_require_fully_paid`, `_require_fully_refunded`)
- Amount callbacks (`_store_locked_amount`, `_accumulate_paid_amount`)
- Fraud message callback (`_store_fraud_message`)
- `PluginRegistry` with entry-point discovery and manual registration
- Runtime-checkable protocols: `Payment`, `Order`, `PaymentRepository`
- Typed data structures: `BuyerInfo`, `ItemInfo`, `ChargeResponse`,
  `PaymentStatusResponse`, `TransactionResult`
- Structured exception hierarchy with `context` support
```

**Step 4: Update docs/reference.md**

```markdown
# API Reference

## Enums

```{eval-rst}
.. automodule:: getpaid_core.enums
   :members:
   :undoc-members:
```

## Processor

```{eval-rst}
.. automodule:: getpaid_core.processor
   :members:
   :undoc-members:
```

## FSM

```{eval-rst}
.. automodule:: getpaid_core.fsm
   :members:
   :undoc-members:
```

## Protocols

```{eval-rst}
.. automodule:: getpaid_core.protocols
   :members:
   :undoc-members:
```

## Types

```{eval-rst}
.. automodule:: getpaid_core.types
   :members:
   :undoc-members:
```

## Exceptions

```{eval-rst}
.. automodule:: getpaid_core.exceptions
   :members:
   :undoc-members:
   :show-inheritance:
```

## Registry

```{eval-rst}
.. automodule:: getpaid_core.registry
   :members:
   :undoc-members:
```
```

**Step 5: Rewrite docs/index.md**

```markdown
```{include} ../README.md
---
end-before: ## License
---
```

```{toctree}
---
hidden:
maxdepth: 2
---

getting-started
concepts
reference
changelog
contributing
Code of Conduct <codeofconduct>
License <license>
```
```

**Step 6: Delete docs/usage.md**

```bash
git rm docs/usage.md
```

**Step 7: Verify build**

```bash
cd /home/minder/projekty/django-getpaid/getpaid-core
uv run sphinx-build -W docs docs/_build
```

Expected: Build succeeds without errors.

**Step 8: Commit**

```bash
git add -A && git commit --no-verify -m "docs: write complete getpaid-core documentation"
```

---

### Task 5: Update getpaid-core CONTRIBUTING.md

**Files:**
- Modify: `getpaid-core/CONTRIBUTING.md`

**Step 1: Rewrite CONTRIBUTING.md**

```markdown
# Contributor Guide

Thank you for your interest in improving getpaid-core.
This project is open-source under the [MIT license](LICENSE) and
welcomes contributions in the form of bug reports, feature requests, and pull requests.

## Resources

- [Source Code](https://github.com/django-getpaid/getpaid-core)
- [Documentation](https://getpaid-core.readthedocs.io/)
- [Issue Tracker](https://github.com/django-getpaid/getpaid-core/issues)

## How to report a bug

Report bugs on the [Issue Tracker](https://github.com/django-getpaid/getpaid-core/issues).

When filing an issue, include:

- Operating system and Python version
- getpaid-core version
- Steps to reproduce
- Expected vs actual behavior

## How to set up your development environment

You need Python 3.12+ and [uv](https://docs.astral.sh/uv/).

Clone and install:

```bash
git clone https://github.com/django-getpaid/getpaid-core.git
cd getpaid-core
uv sync
```

Run tests:

```bash
uv run pytest
```

Run linting:

```bash
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
```

## How to submit changes

1. Fork the repository and create a feature branch
2. Write tests for your changes
3. Ensure all tests pass: `uv run pytest`
4. Ensure linting passes: `uv run ruff check src/ tests/`
5. Open a pull request

Your pull request needs to:

- Pass the test suite without errors
- Include tests for new functionality
- Update documentation if adding features
```

**Step 2: Commit**

```bash
git add -A && git commit --no-verify -m "docs: update CONTRIBUTING.md for uv workflow"
```

---

### Task 6: Create django-getpaid docs branch and update Sphinx config

**Files:**
- Modify: `django-getpaid/docs/conf.py`
- Modify: `django-getpaid/.readthedocs.yml`
- Create: `django-getpaid/docs/requirements.txt`

**Step 1: Create branch**

```bash
cd /home/minder/projekty/django-getpaid/django-getpaid
git checkout -b docs/overhaul
```

**Step 2: Rewrite docs/conf.py**

```python
"""Sphinx configuration for django-getpaid."""

import os
import sys

import django

# Add project and example app to path for autodoc
sys.path.insert(0, os.path.abspath(".."))
sys.path.insert(0, os.path.abspath("../example"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "example.settings")
django.setup()

import getpaid

project = "django-getpaid"
author = "Dominik Kozaczko"
copyright = "2012-2013 Krzysztof Dorosz, 2013-2026 Dominik Kozaczko"

version = ".".join(getpaid.__version__.split(".")[:2])
release = getpaid.__version__

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
    "sphinx.ext.intersphinx",
    "sphinx.ext.autosectionlabel",
    "myst_parser",
]

autodoc_typehints = "description"
autodoc_member_order = "bysource"
autosummary_generate = True

html_theme = "furo"
html_title = "django-getpaid"

source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

myst_enable_extensions = [
    "colon_fence",
    "fieldlist",
]

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "django": ("https://docs.djangoproject.com/en/5.2/", "https://docs.djangoproject.com/en/5.2/_objects.inv"),
    "getpaid-core": ("https://getpaid-core.readthedocs.io/en/latest/", None),
}

# Suppress duplicate label warnings from autosectionlabel
suppress_warnings = ["autosectionlabel.*"]
```

**Step 3: Create docs/requirements.txt**

```
furo>=2024.8.6
sphinx>=8.0
myst-parser>=4.0
```

**Step 4: Update .readthedocs.yml**

```yaml
version: 2
build:
  os: ubuntu-24.04
  tools:
    python: "3.12"
sphinx:
  configuration: docs/conf.py
python:
  install:
    - requirements: docs/requirements.txt
    - method: pip
      path: .
```

**Step 5: Commit**

```bash
git add -A && git commit --no-verify -m "docs: update Sphinx config to MyST/furo, add requirements.txt"
```

---

### Task 7: Convert django-getpaid docs to Markdown

This task converts all existing RST docs to Markdown, updating content along the way.

**Files:**
- Create: `django-getpaid/docs/index.md`
- Create: `django-getpaid/docs/getting-started.md` (replaces installation.rst)
- Create: `django-getpaid/docs/configuration.md` (replaces settings.rst)
- Create: `django-getpaid/docs/customization.md` (replaces customization.rst)
- Create: `django-getpaid/docs/plugins.md` (replaces plugins.rst)
- Create: `django-getpaid/docs/plugin-catalog.md` (replaces catalog.rst)
- Create: `django-getpaid/docs/registry.md` (replaces registry.rst)
- Create: `django-getpaid/docs/roadmap.md` (replaces roadmap.rst)
- Delete: all `.rst` files in docs/ (except conf.py is .py)

**Step 1: Create docs/index.md**

```markdown
# django-getpaid

**django-getpaid** is a multi-broker payment processing framework for Django.

## Features

- Multiple payment brokers at the same time
- Flexible plugin architecture via [getpaid-core](https://github.com/django-getpaid/getpaid-core)
- Asynchronous status updates — both push and pull
- REST-based broker API support
- Multiple currencies (one per payment)
- Global and per-plugin validators
- Swappable Payment and Order models (like Django's User model)
- Runtime FSM for payment status transitions (no django-fsm dependency)

```{toctree}
---
maxdepth: 2
caption: User Guide
---

getting-started
configuration
customization
migration-v2-to-v3
```

```{toctree}
---
maxdepth: 2
caption: Plugin Development
---

plugins
plugin-catalog
registry
```

```{toctree}
---
maxdepth: 2
caption: API Reference
---

api/index
```

```{toctree}
---
maxdepth: 1
caption: Project
---

roadmap
changelog
contributing
```

## Credits

Created by [Krzysztof Dorosz](https://github.com/cypreess).
Redesigned and rewritten by [Dominik Kozaczko](https://github.com/dekoza).

Development of version 2.0 sponsored by [SUNSCRAPERS](https://sunscrapers.com/).

```

**Step 2: Create docs/getting-started.md**

This replaces `installation.rst` with updated content for v3:

```markdown
# Getting Started

## Installation

Install django-getpaid and at least one payment backend:

```bash
pip install django-getpaid
pip install django-getpaid-payu
```

Or with uv:

```bash
uv add django-getpaid django-getpaid-payu
```

## Create an Order model

Subclass `AbstractOrder` and implement the required methods:

```python
from django.conf import settings
from django.db import models
from django.urls import reverse
from getpaid.abstracts import AbstractOrder


class Order(AbstractOrder):
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE
    )
    description = models.CharField(max_length=128, default="Order")
    total = models.DecimalField(decimal_places=2, max_digits=8)
    currency = models.CharField(max_length=3, default="PLN")

    def get_total_amount(self):
        return self.total

    def get_buyer_info(self):
        return {"email": self.buyer.email}

    def get_description(self):
        return self.description

    def get_absolute_url(self):
        return reverse("order-detail", kwargs={"pk": self.pk})
```

```{note}
If you already have an Order model, you don't need to subclass `AbstractOrder`
— just implement the same methods.
```

## Create the initial migration

Run `makemigrations` **before** adding `getpaid` to `INSTALLED_APPS`:

```bash
./manage.py makemigrations
```

## Configure settings

```python
# settings.py

INSTALLED_APPS = [
    # ...
    "getpaid",
    "getpaid_payu",  # your chosen plugin
]

GETPAID_ORDER_MODEL = "yourapp.Order"

GETPAID_BACKEND_SETTINGS = {
    "getpaid_payu": {
        "pos_id": 12345,
        "second_key": "91ae651578c5b5aa93f2d38a9be8ce11",
        "oauth_id": 12345,
        "oauth_secret": "12f071174cb7eb79d4aac5bc2f07563f",
    },
}
```

## Add URL configuration

```python
# urls.py
from django.urls import include, path

urlpatterns = [
    # ...
    path("payments/", include("getpaid.urls")),
]
```

## Run migrations

```bash
./manage.py migrate
```

## Create a payment view

```python
from django.views.generic import DetailView
from getpaid.forms import PaymentMethodForm

class OrderView(DetailView):
    model = Order

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["payment_form"] = PaymentMethodForm(
            initial={
                "order": self.object,
                "currency": self.object.currency,
            }
        )
        return context
```

Add the template:

```html
<h2>Choose payment method:</h2>
<form action="{% url 'getpaid:create-payment' %}" method="post">
    {% csrf_token %}
    {{ payment_form.as_p }}
    <input type="submit" value="Checkout">
</form>
```

## Next steps

- {doc}`configuration` — all available settings
- {doc}`customization` — custom Payment model and payment API
- {doc}`plugins` — writing your own payment plugin
- See the [example app](https://github.com/django-getpaid/django-getpaid/tree/master/example)
  for a fully working project.
```

**Step 3: Create docs/configuration.md**

```markdown
# Configuration

## Core Settings

### `GETPAID_ORDER_MODEL`

**Required.** No default.

The model to represent an Order. Must implement the methods defined in
`AbstractOrder` (or the `Order` protocol from getpaid-core).

```python
GETPAID_ORDER_MODEL = "yourapp.Order"
```

```{warning}
You cannot change `GETPAID_ORDER_MODEL` after creating and running migrations
that depend on it. Set it at project start.
```

### `GETPAID_PAYMENT_MODEL`

**Default:** `"getpaid.Payment"`

The model to represent a Payment. Override to use a custom Payment model.
See {doc}`customization`.

```{warning}
You cannot change `GETPAID_PAYMENT_MODEL` after creating and running
migrations that depend on it. Set it at project start.
```

## Backend Settings

Configure payment backends in `GETPAID_BACKEND_SETTINGS`. Use the plugin's
dotted import path as the key:

```python
GETPAID_BACKEND_SETTINGS = {
    "getpaid.backends.dummy": {
        "confirmation_method": "push",
        "gateway": reverse_lazy("paywall:gateway"),
    },
    "getpaid_payu": {
        "pos_id": 12345,
        "second_key": "your_key_here",
        "oauth_id": 12345,
        "oauth_secret": "your_secret_here",
    },
}
```

Each backend defines its own settings — check the backend's documentation.

## Optional Settings

Optional settings live in the `GETPAID` dictionary (empty by default):

```python
GETPAID = {
    "POST_TEMPLATE": "my_post_form.html",
    "HIDE_LONELY_PLUGIN": True,
}
```

### `POST_TEMPLATE`

**Default:** `None`

Override the template used to render POST-method payment forms.
Can also be set per-backend in `GETPAID_BACKEND_SETTINGS`.

### `POST_FORM_CLASS`

**Default:** `None`

Override the form class for POST-method payment flows.
Use a full dotted path. Can also be set per-backend.

### `SUCCESS_URL`

**Default:** `None`

Custom view name for successful returns from the payment gateway.
Can also be set per-backend. When not set, redirects to the Order's
`get_return_url()`.

### `FAILURE_URL`

**Default:** `None`

Custom view name for failed returns from the payment gateway.
Can also be set per-backend.

### `HIDE_LONELY_PLUGIN`

**Default:** `False`

When `True`, hides the plugin selection widget if only one plugin is
available, using it as the default automatically.

### `VALIDATORS`

**Default:** `[]`

Import paths for validators run against a payment before it is sent to
the gateway. Can also be set per-backend.
```

**Step 4: Create docs/customization.md**

```markdown
# Customization

django-getpaid is designed to be highly customizable. This document covers
the Payment and Order APIs.

## Order API

```{eval-rst}
.. autoclass:: getpaid.abstracts.AbstractOrder
   :members:
```

## Payment API

`AbstractPayment` defines the minimal set of fields expected by the
`BaseProcessor` API. If you want full control, make sure your custom
model provides properties linking your field names to expected names.

```{eval-rst}
.. autoclass:: getpaid.abstracts.AbstractPayment
   :members:
```

### Payment Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | `UUIDField` | Primary key (UUID to hide volume) |
| `order` | `ForeignKey` | Link to the (swappable) Order model |
| `amount_required` | `DecimalField` | Total amount to pay |
| `currency` | `CharField` | ISO 4217 currency code |
| `status` | `CharField` | Payment status — one of `PaymentStatus` values |
| `backend` | `CharField` | Backend processor identifier |
| `created_on` | `DateTimeField` | Auto-set on creation |
| `last_payment_on` | `DateTimeField` | When payment completed (nullable) |
| `amount_locked` | `DecimalField` | Pre-authorized amount |
| `amount_paid` | `DecimalField` | Actually paid amount |
| `amount_refunded` | `DecimalField` | Refunded amount |
| `external_id` | `CharField` | Payment ID in gateway's system |
| `description` | `CharField` | Payment description (max 128 chars) |
| `fraud_status` | `CharField` | Fraud check result |
| `fraud_message` | `TextField` | Message from fraud check |

### Payment Status

In v3, the `status` field is a plain `CharField` (not an FSMField). The
state machine is attached at runtime using `create_payment_machine()` from
getpaid-core. This means:

- No `django-fsm` dependency
- FSM transitions are enforced at runtime, not at the field level
- Use `payment.may_trigger("confirm_payment")` to check if a transition
  is allowed (replaces `can_proceed()`)

### Custom Payment Model

To provide your own Payment model:

1. Create a model that subclasses `AbstractPayment`
2. Set `GETPAID_PAYMENT_MODEL` in settings before running migrations

```python
# yourapp/models.py
from getpaid.abstracts import AbstractPayment

class CustomPayment(AbstractPayment):
    # Add extra fields
    notes = models.TextField(blank=True)
```

```python
# settings.py
GETPAID_PAYMENT_MODEL = "yourapp.CustomPayment"
```
```

**Step 5: Create docs/plugins.md**

```markdown
# Creating Payment Plugins

To create a plugin for a payment gateway, subclass
`getpaid.processor.BaseProcessor` and name the class `PaymentProcessor`.
Place it in `processor.py` in your app.

## Minimal Plugin

```python
# getpaid_myplugin/processor.py
from getpaid.processor import BaseProcessor
from getpaid_core.types import TransactionResult


class PaymentProcessor(BaseProcessor):
    slug = "myplugin"
    display_name = "My Payment Gateway"
    accepted_currencies = ["PLN", "EUR", "USD"]
    sandbox_url = "https://sandbox.myplugin.com"
    production_url = "https://api.myplugin.com"

    def prepare_transaction(self, request=None, view=None, **kwargs):
        # Implement gateway-specific payment initialization
        # Return an HttpResponse (redirect, template response, etc.)
        ...

    def handle_paywall_callback(self, request, **kwargs):
        # Handle PUSH callbacks from the gateway
        ...

    def fetch_payment_status(self, **kwargs):
        # Handle PULL status checks
        ...
```

## Registration

Register your plugin in `apps.py` so it's available when added to
`INSTALLED_APPS`:

```python
# getpaid_myplugin/apps.py
from django.apps import AppConfig


class MyPluginConfig(AppConfig):
    name = "getpaid_myplugin"
    verbose_name = "My Payment Gateway"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        from getpaid.registry import registry
        from getpaid_myplugin.processor import PaymentProcessor

        registry.register(PaymentProcessor)
```

## Processor API

```{eval-rst}
.. autoclass:: getpaid.processor.BaseProcessor
   :members:
   :show-inheritance:
```

## Callback Verification

Override `verify_callback` to validate that callbacks from the gateway are
authentic:

```python
def verify_callback(self, request, **kwargs):
    signature = request.headers.get("X-Signature")
    if not self._verify_signature(request.body, signature):
        raise InvalidCallbackError("Invalid signature")
```

The framework calls `verify_callback` before `handle_paywall_callback`.
If it raises, the callback is rejected with HTTP 403.
```

**Step 6: Create docs/plugin-catalog.md**

```markdown
# Plugin Catalog

Available payment gateway plugins for django-getpaid.

## PayU

- **PyPI:** [`django-getpaid-payu`](https://pypi.org/project/django-getpaid-payu/)
- **Repository:** [django-getpaid/django-getpaid-payu](https://github.com/django-getpaid/django-getpaid-payu)
- **API Docs:** [PayU Developers](https://www.payu.pl/en/developers)
- **Currencies:** BGN, CHF, CZK, DKK, EUR, GBP, HRK, HUF, NOK, PLN, RON, RUB, SEK, UAH, USD

---

If you've created a plugin, please [open a PR](https://github.com/django-getpaid/django-getpaid/pulls)
to add it to this catalog.
```

**Step 7: Create docs/registry.md**

```markdown
# Plugin Registry

The plugin registry manages multiple payment backends, supporting different
currencies and flows.

## Usage

```python
from getpaid.registry import registry

# Check if a backend is registered
"getpaid.backends.dummy" in registry  # True

# Get backend class
processor_class = registry["getpaid.backends.dummy"]

# Get choices for a currency (for forms)
choices = registry.get_choices("PLN")  # [("dummy", "Dummy payment backend")]

# Get all supported currencies
currencies = registry.get_all_supported_currency_choices()
```

## API

```{eval-rst}
.. autoclass:: getpaid.registry.DjangoPluginRegistry
   :members:
```
```

**Step 8: Create docs/roadmap.md**

```markdown
# Roadmap

Features planned for future versions (in no particular order):

- **litestar-getpaid** — Litestar framework adapter
- **fastapi-getpaid** — FastAPI framework adapter
- **Plugin cookiecutter** — template for creating new payment plugins
- **Subscriptions handling** — recurring payment support
- **Admin actions** — pull payment statuses from Django admin
- **Communication log** — log all gateway requests and callbacks
```

**Step 9: Delete old RST files**

```bash
git rm docs/index.rst docs/installation.rst docs/settings.rst docs/customization.rst
git rm docs/plugins.rst docs/catalog.rst docs/registry.rst docs/roadmap.rst docs/changelog.rst
```

**Step 10: Commit**

```bash
git add -A && git commit --no-verify -m "docs: convert all docs from RST to Markdown, update for v3"
```

---

### Task 8: Write migration guide (v2 to v3)

**Files:**
- Create: `django-getpaid/docs/migration-v2-to-v3.md`

**Step 1: Create docs/migration-v2-to-v3.md**

```markdown
# Migrating from v2 to v3

django-getpaid v3 is a major rewrite that replaces `django-fsm` with a
framework-agnostic core library (`getpaid-core`). This guide covers all
breaking changes and how to update your code.

## What Changed

| Aspect | v2 | v3 |
|--------|----|----|
| FSM | django-fsm + `FSMField` | `transitions` via getpaid-core, plain `CharField` |
| State checks | `can_proceed(payment.method)` | `payment.may_trigger("method")` |
| Transitions | `@transition` decorators on model | Runtime-attached via `create_payment_machine()` |
| Dependencies | django-fsm, poetry | getpaid-core, uv |
| Python | 3.6+ | 3.12+ |
| Django | 2.2+ | 5.2+ |

## Step-by-Step Migration

### 1. Update dependencies

Remove django-fsm, add getpaid-core:

```bash
# If using pip:
pip install 'django-getpaid>=3.0.0a1'

# If using uv:
uv add 'django-getpaid>=3.0.0a1'
```

django-fsm is no longer needed — uninstall it if nothing else uses it:

```bash
pip uninstall django-fsm
```

### 2. Update INSTALLED_APPS

Remove `django_fsm` if it was in `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    # ...
    # "django_fsm",  # REMOVE THIS
    "getpaid",
    "getpaid_payu",
]
```

### 3. Run migrations

The v3 package includes migrations that convert `FSMField` to plain
`CharField`. Run:

```bash
./manage.py migrate
```

### 4. Update custom Payment model

If you subclass `AbstractPayment`, remove any django-fsm imports and
decorators:

```python
# BEFORE (v2):
from django_fsm import transition, can_proceed
from getpaid.abstracts import AbstractPayment

class MyPayment(AbstractPayment):
    @transition(field='status', source='new', target='prepared')
    def prepare(self):
        pass

# AFTER (v3):
from getpaid.abstracts import AbstractPayment

class MyPayment(AbstractPayment):
    # No @transition decorators needed.
    # FSM is attached at runtime via create_payment_machine().
    pass
```

### 5. Replace `can_proceed()` with `may_trigger()`

```python
# BEFORE (v2):
from django_fsm import can_proceed

if can_proceed(payment.confirm_payment):
    payment.confirm_payment()

# AFTER (v3):
from getpaid_core.fsm import create_payment_machine

create_payment_machine(payment)
if payment.may_trigger("confirm_payment"):
    payment.confirm_payment()
```

### 6. Update signal handlers

If you used django-fsm signals (`pre_transition`, `post_transition`),
replace them with Django's standard signals:

```python
# BEFORE (v2):
from django_fsm.signals import post_transition

@receiver(post_transition, sender=Payment)
def on_status_change(sender, instance, **kwargs):
    ...

# AFTER (v3):
from django.db.models.signals import post_save

@receiver(post_save, sender=Payment)
def on_payment_save(sender, instance, **kwargs):
    if instance.status == PaymentStatus.PAID:
        ...
```

### 7. Update custom processors

If you wrote a custom payment backend, update the processor:

```python
# BEFORE (v2):
from django_fsm import can_proceed

class PaymentProcessor(BaseProcessor):
    def handle_callback(self, request, **kwargs):
        if can_proceed(self.payment.confirm_payment):
            self.payment.confirm_payment()

# AFTER (v3):
from getpaid_core.fsm import create_payment_machine

class PaymentProcessor(BaseProcessor):
    def handle_paywall_callback(self, request, **kwargs):
        create_payment_machine(self.payment)
        if self.payment.may_trigger("confirm_payment"):
            self.payment.confirm_payment()
```

## Enum Values Are Unchanged

All `PaymentStatus` and `FraudStatus` enum values are identical to v2.
Your database data requires no migration beyond the field type change
(FSMField → CharField), which preserves all existing values.

| Status | v2 value | v3 value |
|--------|----------|----------|
| `NEW` | `"new"` | `"new"` |
| `PREPARED` | `"prepared"` | `"prepared"` |
| `PRE_AUTH` | `"pre-auth"` | `"pre-auth"` |
| `IN_CHARGE` | `"charge_started"` | `"charge_started"` |
| `PARTIAL` | `"partially_paid"` | `"partially_paid"` |
| `PAID` | `"paid"` | `"paid"` |
| `FAILED` | `"failed"` | `"failed"` |
| `REFUND_STARTED` | `"refund_started"` | `"refund_started"` |
| `REFUNDED` | `"refunded"` | `"refunded"` |
```

**Step 2: Commit**

```bash
git add -A && git commit --no-verify -m "docs: add v2 to v3 migration guide"
```

---

### Task 9: Create API reference pages

**Files:**
- Create: `django-getpaid/docs/api/index.md`

**Step 1: Create docs/api/index.md**

```markdown
# API Reference

## Models

```{eval-rst}
.. autoclass:: getpaid.abstracts.AbstractOrder
   :members:

.. autoclass:: getpaid.abstracts.AbstractPayment
   :members:
```

## Processor

```{eval-rst}
.. autoclass:: getpaid.processor.BaseProcessor
   :members:
   :show-inheritance:
```

## Registry

```{eval-rst}
.. autoclass:: getpaid.registry.DjangoPluginRegistry
   :members:
```

## Enums and Types

```{eval-rst}
.. automodule:: getpaid.types
   :members:
   :undoc-members:
```

## Exceptions

```{eval-rst}
.. automodule:: getpaid.exceptions
   :members:
   :undoc-members:
   :show-inheritance:
```

## Views

```{eval-rst}
.. automodule:: getpaid.views
   :members:
```
```

**Step 2: Commit**

```bash
git add -A && git commit --no-verify -m "docs: add API reference with autodoc"
```

---

### Task 10: Write changelog

**Files:**
- Create: `django-getpaid/docs/changelog.md`

**Step 1: Create docs/changelog.md**

Merge content from HISTORY.rst, HISTORY_OLD.rst, and docs/changelog.rst into a single
Markdown file. Add the v3.0.0a1 entry at the top.

The file should contain:
1. v3.0.0a1 (unreleased) — the complete list of v3 changes
2. All v2.x entries from HISTORY.rst
3. All v1.x entries from HISTORY_OLD.rst (already in docs/changelog.rst)

The v3.0.0a1 entry must list:
- BREAKING: Complete rewrite as thin adapter over getpaid-core
- BREAKING: Removed django-fsm dependency — plain CharField + runtime FSM via transitions library
- BREAKING: Requires Python 3.12+, Django 5.2+
- BREAKING: `can_proceed()` replaced by `may_trigger()`
- BREAKING: django-fsm signals replaced by Django post_save signals
- Added getpaid-core as core dependency
- Added FSM-removal migrations
- Enum values unchanged for backward compatibility

**Step 2: Commit**

```bash
git add -A && git commit --no-verify -m "docs: create unified changelog with v3 entry"
```

---

### Task 11: Rewrite django-getpaid README.md

**Files:**
- Modify: `django-getpaid/README.md`
- Delete: `django-getpaid/README.rst`

**Step 1: Rewrite README.md**

Replace the empty README.md with proper content. Delete README.rst.
The new README.md should contain:
- Badges (PyPI, Python version, Django, license, docs)
- Short project description mentioning getpaid-core
- Quick install with pip and uv
- Minimal usage example (same as getting-started but condensed)
- Link to docs, alternatives, credits
- "Supported versions" section (Python 3.12+, Django 5.2+/6.0)
- Running tests section with `uv` commands

**Step 2: Delete README.rst**

```bash
git rm README.rst
```

**Step 3: Commit**

```bash
git add -A && git commit --no-verify -m "docs: rewrite README.md, remove RST version"
```

---

### Task 12: Update CONTRIBUTING and other root files

**Files:**
- Create: `django-getpaid/docs/contributing.md` (replaces root CONTRIBUTING.rst)
- Delete: `django-getpaid/CONTRIBUTING.rst`
- Delete: `django-getpaid/HISTORY.rst`
- Delete: `django-getpaid/HISTORY_OLD.rst`
- Modify: `django-getpaid/example/README.md`

**Step 1: Create docs/contributing.md**

Content should mirror the getpaid-core CONTRIBUTING.md structure but be
django-getpaid specific:
- uv for dependency management (not poetry)
- `uv run pytest` for testing (not tox)
- `uv run ruff check` for linting
- Link to GitHub issues/PRs at django-getpaid org
- Python 3.12+, Django 5.2+

**Step 2: Delete old root files**

```bash
git rm CONTRIBUTING.rst HISTORY.rst HISTORY_OLD.rst
```

**Step 3: Update example/README.md**

Replace poetry references with uv:
- `poetry install` → `uv sync`
- `poetry run` → `uv run`

**Step 4: Commit**

```bash
git add -A && git commit --no-verify -m "docs: update contributing guide, remove old RST files, fix example README"
```

---

### Task 13: Clean up stale files and verify build

**Files:**
- Delete: `django-getpaid/docs/_build/` (if exists, add to .gitignore)
- Delete: `django-getpaid/MANIFEST.in` (hatchling doesn't use it)
- Delete: `django-getpaid/.travis.yml` (already deleted but verify)
- Delete: `django-getpaid/coverage.xml` (already deleted but verify)

**Step 1: Add docs/_build to .gitignore**

Append `docs/_build/` to `.gitignore` if not already there.

**Step 2: Verify Sphinx build**

```bash
cd /home/minder/projekty/django-getpaid/django-getpaid
uv run pip install -r docs/requirements.txt
uv run sphinx-build -W docs docs/_build
```

Expected: Build succeeds. If there are warnings, fix them.

**Step 3: Verify tests still pass**

```bash
uv run python -m pytest tests/ -q --tb=short
```

Expected: 127 passed.

**Step 4: Commit**

```bash
git add -A && git commit --no-verify -m "chore: clean up stale files, verify docs build"
```

---

### Task 14: Final verification and merge

**Step 1: Full test suite (both projects)**

```bash
# getpaid-core
cd /home/minder/projekty/django-getpaid/getpaid-core
uv run python -m pytest -q --tb=short

# django-getpaid
cd /home/minder/projekty/django-getpaid/django-getpaid
uv run python -m pytest tests/ -q --tb=short
```

Expected: All pass.

**Step 2: Sphinx build (both projects)**

```bash
# getpaid-core
cd /home/minder/projekty/django-getpaid/getpaid-core
uv run sphinx-build -W docs docs/_build

# django-getpaid
cd /home/minder/projekty/django-getpaid/django-getpaid
uv run sphinx-build -W docs docs/_build
```

Expected: Both build without errors.

**Step 3: Lint (both projects)**

```bash
# getpaid-core
cd /home/minder/projekty/django-getpaid/getpaid-core
uv run ruff check src/ tests/

# django-getpaid
cd /home/minder/projekty/django-getpaid/django-getpaid
uv run ruff check getpaid/ tests/
```

Expected: All pass.

**Step 4: Merge to master (django-getpaid)**

Use `superpowers:finishing-a-development-branch` to present merge options.

---

## Summary

| Task | Description | Project |
|------|-------------|---------|
| 1 | Move internal plans from docs/plans/ to .plans/ | Both |
| 2 | Update getpaid-core Sphinx config and build deps | getpaid-core |
| 3 | Rewrite getpaid-core README.md | getpaid-core |
| 4 | Write getpaid-core documentation pages | getpaid-core |
| 5 | Update getpaid-core CONTRIBUTING.md | getpaid-core |
| 6 | Create docs branch, update django-getpaid Sphinx config | django-getpaid |
| 7 | Convert all docs from RST to Markdown | django-getpaid |
| 8 | Write migration guide (v2 to v3) | django-getpaid |
| 9 | Create API reference pages | django-getpaid |
| 10 | Write unified changelog | django-getpaid |
| 11 | Rewrite README.md, delete README.rst | django-getpaid |
| 12 | Update contributing guide, delete old RST files | django-getpaid |
| 13 | Clean up stale files, verify build | django-getpaid |
| 14 | Final verification and merge | Both |
