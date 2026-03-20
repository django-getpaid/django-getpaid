# Creating Payment Plugins

To create a plugin for a payment gateway, subclass
`getpaid.processor.BaseProcessor` and name the class `PaymentProcessor`.
Place it in `processor.py` in your app.

## Minimal Plugin

```python
# getpaid_myplugin/processor.py
from getpaid_core.processor import BaseProcessor
from getpaid_core.types import PaymentUpdate, TransactionResult


class PaymentProcessor(BaseProcessor):
    slug = "myplugin"
    display_name = "My Payment Gateway"
    accepted_currencies = ["PLN", "EUR", "USD"]
    sandbox_url = "https://sandbox.myplugin.com"
    production_url = "https://api.myplugin.com"

    async def prepare_transaction(self, **kwargs) -> TransactionResult:
        ...

    async def verify_callback(self, data: dict, headers: dict, **kwargs) -> None:
        ...

    async def handle_callback(
        self, data: dict, headers: dict, **kwargs
    ) -> PaymentUpdate | None:
        ...

    async def fetch_payment_status(self, **kwargs) -> PaymentUpdate | None:
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
   :no-index:
```

## Callback Verification

Override `verify_callback` to validate that callbacks from the gateway are
authentic:

```python
async def verify_callback(self, data, headers, **kwargs):
    signature = headers.get("X-Signature")
    raw_body = kwargs["raw_body"]
    if not self._verify_signature(raw_body, signature):
        raise InvalidCallbackError("Invalid signature")
```

The framework calls `verify_callback` before `handle_callback`.
If it raises, the callback is rejected with HTTP 403.
