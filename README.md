# django-getpaid

[![PyPI version](https://img.shields.io/pypi/v/django-getpaid)](https://pypi.org/project/django-getpaid/)
[![Python versions](https://img.shields.io/pypi/pyversions/django-getpaid)](https://pypi.org/project/django-getpaid/)
[![Django versions](https://img.shields.io/badge/django-5.2%20%7C%206.0-blue)](https://docs.djangoproject.com/)
[![License](https://img.shields.io/pypi/l/django-getpaid)](https://github.com/django-getpaid/django-getpaid/blob/master/LICENSE)
[![Documentation](https://readthedocs.org/projects/django-getpaid/badge/?version=latest)](https://django-getpaid.readthedocs.io/)

**Multi-broker payment processing framework for Django.**

`django-getpaid` is a flexible, modular payment processing wrapper for Django, built on the framework-agnostic [getpaid-core](https://github.com/django-getpaid/python-getpaid-core). It allows you to integrate multiple payment gateways into your application using a unified API.

> **v3.0.0a2 (Alpha)** — This is a major rewrite that introduces framework-agnostic core and removes the `django-fsm` dependency in favor of a runtime state machine.

## Key Features

- **Unified API**: Process payments across different brokers (PayU, Paynow, BitPay, etc.) using the same logic.
- **Pluggable Architecture**: Easily add new payment backends or swap existing ones.
- **Runtime FSM**: Robust payment status management (NEW -> PREPARED -> PAID) without heavy dependencies.
- **Asynchronous Updates**: Built-in support for both push (webhook) and pull (status check) notifications.
- **REST and POST Support**: Handles both modern RESTful APIs and traditional POST-form redirects.
- **Swappable Models**: Customize your Order and Payment models to fit your business logic (uses `swapper`).
- **Template Customization**: Full control over payment selection and confirmation pages.
- **Type Safety**: Built with modern Python types for better IDE support and reliability.

## Installation

Install the package using pip:

```bash
pip install django-getpaid
```

Or using uv:

```bash
uv add django-getpaid
```

You should also install at least one payment backend, for example:

```bash
pip install getpaid-payu getpaid-paynow
```

## Quick Start

### 1. Define your Order model

Subclass `AbstractOrder` and implement the required methods:

```python
from django.db import models
from django.conf import settings
from getpaid.abstracts import AbstractOrder

class Order(AbstractOrder):
    amount = models.DecimalField(decimal_places=2, max_digits=8)
    currency = models.CharField(max_length=3, default="PLN")
    description = models.CharField(max_length=128)
    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    def get_total_amount(self):
        return self.amount

    def get_currency(self):
        return self.currency

    def get_buyer_info(self):
        return {"email": self.buyer.email}

    def get_description(self):
        return self.description
```

### 2. Configure Settings

Add `getpaid` and your chosen backends to `INSTALLED_APPS` and configure the models:

```python
INSTALLED_APPS = [
    # ...
    "getpaid",
    "getpaid_payu",
    "getpaid_paynow",
    "yourapp",
]

GETPAID_ORDER_MODEL = "yourapp.Order"

# Optional: Customize the Payment model
# GETPAID_PAYMENT_MODEL = "yourapp.CustomPayment"

GETPAID_BACKEND_SETTINGS = {
    "getpaid_payu.processor.PayUProcessor": {
        "pos_id": 12345,
        "second_key": "your-second-key",
        "oauth_id": 12345,
        "oauth_secret": "your-oauth-secret",
        "sandbox": True,
    },
    "getpaid_paynow.processor.PaynowProcessor": {
        "api_key": "your-api-key",
        "signature_key": "your-signature-key",
        "sandbox": True,
    },
}
```

### 3. Add URLs

Include `getpaid` URLs in your project's `urls.py`:

```python
from django.urls import include, path

urlpatterns = [
    # ...
    path("payments/", include("getpaid.urls")),
]
```

## Payment Flow

1. **Order Creation**: Create an instance of your `Order` model.
2. **Payment Selection**: Present a form to the user to select a payment method (using `getpaid.forms.PaymentForm`).
3. **Redirection**: `getpaid` prepares the transaction and redirects the user to the payment provider's paywall.
4. **Callback**: The provider sends a notification (push) or the application checks the status (pull).
5. **State Update**: The payment's status is automatically updated (e.g., to `PAID` or `FAILED`).

## Template Customization

You can customize the payment selection page by overriding the `getpaid/payment_form.html` template. To customize the automatic redirect page (used for POST-based gateways), override `getpaid/payment_post_form.html`.

## Example Application

The repository contains a comprehensive **example application** that demonstrates:
- Integration with multiple backends (Dummy, PayU, Paynow).
- Custom Order and Payment models.
- Environment-based configuration.
- Error handling and success/failure pages.

Check it out at [https://github.com/django-getpaid/django-getpaid/tree/master/example/](https://github.com/django-getpaid/django-getpaid/tree/master/example/).

## Ecosystem

`django-getpaid` is part of a larger ecosystem:

- **Core**: [getpaid-core](https://github.com/django-getpaid/python-getpaid-core) — Framework-agnostic logic.
- **Other Wrappers**: 
  - [litestar-getpaid](https://github.com/django-getpaid/litestar-getpaid)
  - [fastapi-getpaid](https://github.com/django-getpaid/fastapi-getpaid)
- **Official Processors**:
  - [getpaid-payu](https://github.com/django-getpaid/getpaid-payu)
  - [getpaid-paynow](https://github.com/django-getpaid/getpaid-paynow)
  - [getpaid-bitpay](https://github.com/django-getpaid/getpaid-bitpay)
  - [getpaid-przelewy24](https://github.com/django-getpaid/getpaid-przelewy24)

## Migrating from v2

If you are upgrading from `django-getpaid` v2.x, please refer to our [Migration Guide](https://github.com/django-getpaid/django-getpaid/blob/master/docs/migration-v2-to-v3.md) for a detailed list of breaking changes and step-by-step instructions.

## License

This project is licensed under the MIT License.

## Credits

Created by [Krzysztof Dorosz](https://github.com/cypreess).
Redesigned and rewritten by [Dominik Kozaczko](https://github.com/dekoza).

---
*This project is not affiliated with the [getpaid](https://code.google.com/archive/p/getpaid/) Plone project.*
