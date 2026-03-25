"""Django-specific plugin registry wrapping getpaid-core."""

import importlib

from django.urls import include, path
from getpaid_core.processor import BaseProcessor
from getpaid_core.registry import PluginRegistry as CorePluginRegistry
from getpaid_core.registry import registry as core_registry


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
        return self.get_by_slug(item)

    def get_by_slug(self, item):
        self._sync_aliases_from_core()
        slug = self._module_map.get(item) or item
        return self._core.get_by_slug(slug)

    def resolve_backend(self, item: str) -> str:
        return self.get_by_slug(item).slug

    def get_aliases(self, item: str) -> set[str]:
        processor = self.get_by_slug(item)
        aliases = {processor.slug}
        aliases.update(
            alias
            for alias, slug in self._module_map.items()
            if slug == processor.slug
        )
        return aliases

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
            self._remember_aliases(module_or_proc)
            return

        # Module-based registration (v2 backward compat)
        processor = module_or_proc.processor.PaymentProcessor
        self._core.register(processor)
        self._remember_aliases(processor)
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
            self.get_by_slug(item)
            return True
        except KeyError:
            return False

    def _all_keys(self):
        """Return all keys (both module paths and slugs)."""
        self._sync_aliases_from_core()
        keys = set(self._module_map.keys())
        keys.update(self._core._backends.keys())
        return keys

    def _remember_aliases(self, processor_class):
        class_module = processor_class.__module__
        self._module_map[class_module] = processor_class.slug
        self._module_map[f'{class_module}.{processor_class.__name__}'] = (
            processor_class.slug
        )
        if class_module.endswith('.processor'):
            backend_module = class_module.rsplit('.', 1)[0]
            self._module_map[backend_module] = processor_class.slug

    def _sync_aliases_from_core(self):
        self._core._ensure_discovered()
        for processor_class in self._core._backends.values():
            self._remember_aliases(processor_class)


# Module-level singleton wrapping core's singleton
registry = DjangoPluginRegistry(core_registry)
