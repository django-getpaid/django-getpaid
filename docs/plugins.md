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
