# django-getpaid

[![PyPI](https://img.shields.io/pypi/v/django-getpaid.svg)](https://pypi.org/project/django-getpaid/)
[![Python Version](https://img.shields.io/pypi/pyversions/django-getpaid)](https://pypi.org/project/django-getpaid/)
[![Django Version](https://img.shields.io/badge/django-5.2%2B-blue)](https://docs.djangoproject.com/)
[![License](https://img.shields.io/pypi/l/django-getpaid)](https://pypi.org/project/django-getpaid/)
[![Documentation](https://readthedocs.org/projects/django-getpaid/badge/?version=latest)](https://django-getpaid.readthedocs.io/)

Multi-broker payment processing framework for Django, built on
[getpaid-core](https://github.com/django-getpaid/python-getpaid-core).

> **v3.0.0a1 (Alpha)** — This is a pre-release. The API may change before the
> stable v3.0 release.

## Features

- Multiple payment brokers at the same time
- Flexible plugin architecture via getpaid-core
- Asynchronous status updates -- both push and pull
- REST-based broker API support
- Multiple currencies (one per payment)
- Global and per-plugin validators
- Swappable Payment and Order models (like Django's User model)
- Runtime FSM for payment status transitions (no django-fsm dependency)

## Installation

```bash
pip install django-getpaid
```

Or with uv:

```bash
uv add django-getpaid
```

Then install a payment backend plugin (check that the plugin supports v3
before installing — v2 plugins are **not** compatible):

## Quick Start

Define an Order model:

```python
from getpaid.abstracts import AbstractOrder

class Order(AbstractOrder):
    amount = models.DecimalField(decimal_places=2, max_digits=8)
    description = models.CharField(max_length=128)
    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    def get_total_amount(self):
        return self.amount

    def get_buyer_info(self):
        return {"email": self.buyer.email}

    def get_description(self):
        return self.description
```

Configure settings:

```python
INSTALLED_APPS = [
    # ...
    "getpaid",
    "getpaid_payu",
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

Add URL configuration:

```python
urlpatterns = [
    # ...
    path("payments/", include("getpaid.urls")),
]
```

See the [full documentation](https://django-getpaid.readthedocs.io/) for
details on configuration, customization, plugin development, and migration
from v2.

## Supported Versions

- **Python:** 3.12+
- **Django:** 5.2+

## Running Tests

```bash
uv sync
uv run pytest
```

Or with ruff for linting:

```bash
uv run ruff check getpaid/ tests/
```

## Alternatives

- [django-payments](https://github.com/mirumee/django-payments)

## Credits

Created by [Krzysztof Dorosz](https://github.com/cypreess).
Redesigned and rewritten by [Dominik Kozaczko](https://github.com/dekoza).

Development of version 2.0 sponsored by [SUNSCRAPERS](https://sunscrapers.com/).

## Disclaimer

This project has nothing in common with the
[getpaid](https://code.google.com/archive/p/getpaid/) plone project.
