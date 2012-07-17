from django.conf import settings
import sys

def import_backend_modules(submodule=None):
    backends = getattr(settings, 'GETPAID_BACKENDS', [])
    modules = {}
    for backend_name in backends:
        fqmn = backend_name
        if submodule:
            fqmn = '%s.%s' % (fqmn, submodule)
        __import__(fqmn)
        module = sys.modules[fqmn]
        modules[backend_name] = module
    return modules


def get_backend_choices(currency=None):
    """
    Get active backends modules. Backend list can be filtered by supporting given currency.
    """
    choices = []
    backends = import_backend_modules()
    if currency:
        for backend in backends.keys():
            if currency not in backends[backend].PaymentProcessor.BACKEND_ACCEPTED_CURRENCY:
                del backends[backend]
    for name, module in backends.items():
        choices.append((name, module.PaymentProcessor.BACKEND_NAME))
    return choices

def get_backend_settings(backend):
    """
    Returns backend settings. If it does not exist it fails back to empty dict().
    """
    backends_settings = getattr(settings, 'GETPAID_BACKENDS_SETTINGS', {})
    try:
        return backends_settings[backend]
    except KeyError:
        return {}