import importlib

from django.urls import include, path


def importable(name):
    try:
        importlib.import_module(name)
        return True
    except ImportError:
        return False


class PluginRegistry(object):
    def __init__(self):
        self._backends = {}

    def register(self, plugin):
        self._backends[plugin.__name__] = plugin.processor.PaymentProcessor

    def get_choices(self, currency):
        currency = currency.upper()
        return [
            (name, p.title)
            for name, p in self._backends.items() if currency in p.get_accepted_currencies()]

    @property
    def urls(self):
        return [
            path('{}/'.format(p.slug), include(('{}.urls'.format(name), p.slug), namespace=p.slug))
            for name, p in self._backends.items()
            if importable('{}.urls'.format(name))
        ]


registry = PluginRegistry()
