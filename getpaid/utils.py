# coding: utf8
import sys
from collections import OrderedDict
from importlib import import_module

from django.apps import apps
from django.conf import settings
from django.utils import six
from django.core.urlresolvers import reverse
from django.utils.functional import SimpleLazyObject
from django.utils.six.moves.urllib.parse import parse_qsl
import django

Site = SimpleLazyObject(lambda: apps.get_model('sites.Site'))

if six.PY3:
    unicode = str


def import_name(name):
    return import_module(name)


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
    Get active backends modules. Backend list can be filtered by
    supporting given currency.
    """
    choices = []
    backends_names = getattr(settings, 'GETPAID_BACKENDS', [])

    for backend_name in backends_names:
        backend = import_name(backend_name)
        if currency:
            if currency in backend.PaymentProcessor.BACKEND_ACCEPTED_CURRENCY:
                choices.append(
                    (backend_name, backend.PaymentProcessor.BACKEND_NAME)
                )
        else:
            choices.append(
                (backend_name, backend.PaymentProcessor.BACKEND_NAME)
            )
    return choices


def get_backend_settings(backend):
    """
    Returns backend settings.
    If it does not exist it fails back to empty dict().
    """
    backends_settings = getattr(settings, 'GETPAID_BACKENDS_SETTINGS', {})
    try:
        return backends_settings[backend]
    except KeyError:
        return {}


def build_absolute_uri(view_name, scheme='https', domain=None,
                       reverse_args=None, reverse_kwargs=None):
    if not reverse_args:
        reverse_args = ()
    if not reverse_kwargs:
        reverse_kwargs = {}
    if domain is None:
        domain = get_domain()

    path = reverse(view_name, args=reverse_args, kwargs=reverse_kwargs)
    domain = domain.rstrip('/')
    path = path.lstrip('/')

    return u"{0}://{1}/{2}".format(scheme, domain, path)


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


def get_domain(request=None):
    if (hasattr(settings, 'GETPAID_SITE_DOMAIN') and
            settings.GETPAID_SITE_DOMAIN):
        return settings.GETPAID_SITE_DOMAIN
    if django.VERSION[:2] >= (1, 8):
        site = Site.objects.get_current(request=request)
    else:
        site = Site.objects.get_current()

    return site.domain
