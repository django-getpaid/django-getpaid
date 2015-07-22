# coding: utf8
import sys
from collections import OrderedDict

from django.conf import settings
from django.utils import six
from django.core.urlresolvers import reverse
from django.utils.six.moves.urllib.parse import parse_qsl


if six.PY3:
    unicode = str


def import_name(name):
    components = name.split('.')

    if len(components) == 1:
        # direct module, import the module directly
        mod = __import__(name, globals(), locals(), [name])
    else:
        # the module is within another, so we
        # need to import it from there
        parent_path = components[0:-1]
        module_name = components[-1]

        parent_mod = __import__(
            '.'.join(parent_path), globals(), locals(), [module_name])
        mod = getattr(parent_mod, components[-1])

    return mod


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


def build_absolute_uri_for_site(site, view_name, scheme='https',
                                reverse_args=None, reverse_kwargs=None):
    domain = site.domain
    if not reverse_args:
        reverse_args = ()
    if not reverse_kwargs:
        reverse_kwargs = {}
    path = reverse(view_name, args=reverse_args, kwargs=reverse_kwargs)
    return u"{0}://{1}{2}".format(scheme, domain, path)


def qs_to_ordered_params(query_string):
    params_list = parse_qsl(unicode(query_string))
    params = OrderedDict()
    for field, value in params_list:
        if isinstance(value, (list, tuple)):
            value = value[0]
        if isinstance(value, six.binary_type):
            value = value.decode('utf8')
        if isinstance(field, six.binary_type):
            field = field.decode('utf8')
        params[field] = value
    return params
