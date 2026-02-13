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
