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
        return item in self._module_map or self._has_slug(item)

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
            # Derive backend module path for backward-compat lookups.
            # E.g. 'getpaid.backends.dummy.processor' -> 'getpaid.backends.dummy'
            class_module = module_or_proc.__module__
            if class_module.endswith('.processor'):
                backend_module = class_module.rsplit('.', 1)[0]
                self._module_map[backend_module] = module_or_proc.slug
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
