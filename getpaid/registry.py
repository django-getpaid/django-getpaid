import importlib

from django.urls import include, path

from getpaid.processor import BaseProcessor


def importable(name):
    try:
        importlib.import_module(name)
        return True
    except ImportError:
        return False


class PluginRegistry(object):
    def __init__(self):
        self._backends = {}

    def __contains__(self, item):
        return item in self._backends

    def __getitem__(self, item):
        return self._backends[item]

    def __iter__(self):
        return iter(self._backends)

    def register(self, module_or_proc):
        if hasattr(module_or_proc, "__base__") and issubclass(
            module_or_proc, BaseProcessor
        ):
            self._backends[module_or_proc.slug] = module_or_proc
        else:
            processor = module_or_proc.processor.PaymentProcessor
            self._backends[processor.slug] = processor

    def get_choices(self, currency):
        currency = currency.upper()
        return [
            (name, p.display_name)
            for name, p in self._backends.items()
            if currency in p.get_accepted_currencies()
        ]

    @property
    def urls(self):
        return [
            path(
                "{}/".format(p.slug),
                include(("{}.urls".format(name), p.slug), namespace=p.slug),
            )
            for name, p in self._backends.items()
            if importable("{}.urls".format(name))
        ]

    def get_all_supported_currency_choices(self):
        currencies = set()
        for backend in self._backends:
            currencies.update(backend.accepted_currencies or [])
        return [(c.upper(), c.upper()) for c in currencies]


registry = PluginRegistry()
