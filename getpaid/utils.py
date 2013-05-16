from django.conf import settings
import sys


def import_name(name):
    components = name.split('.')
    mod = __import__('.'.join(components[0:-1]), globals(), locals(), [components[-1]] )
    return getattr(mod, components[-1])


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
    backends_names = getattr(settings, 'GETPAID_BACKENDS', [])

    for backend_name in backends_names:
        backend = import_name(backend_name)
        if currency:
            if currency in backend.PaymentProcessor.BACKEND_ACCEPTED_CURRENCY:
                choices.append((backend_name, backend.PaymentProcessor.BACKEND_NAME, ))
        else:
            choices.append((backend_name, backend.PaymentProcessor.BACKEND_NAME, ))
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