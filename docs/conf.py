"""Sphinx configuration for django-getpaid."""

import os
import sys

import django

# Add project and example app to path for autodoc
sys.path.insert(0, os.path.abspath('..'))
sys.path.insert(0, os.path.abspath('../example'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'example.settings')
django.setup()

import getpaid

project = 'django-getpaid'
author = 'Dominik Kozaczko'
copyright = '2012-2013 Krzysztof Dorosz, 2013-2026 Dominik Kozaczko'

version = '.'.join(getpaid.__version__.split('.')[:2])
release = getpaid.__version__

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    'sphinx.ext.intersphinx',
    'sphinx.ext.autosectionlabel',
    'myst_parser',
]

autodoc_typehints = 'description'
autodoc_member_order = 'bysource'

html_theme = 'furo'
html_title = 'django-getpaid'

source_suffix = {
    '.md': 'markdown',
}

myst_enable_extensions = [
    'colon_fence',
    'fieldlist',
]

intersphinx_mapping = {
    'python': ('https://docs.python.org/3', None),
    # Django and getpaid-core intersphinx will work on ReadTheDocs.
    # Uncomment when building with network access:
    # 'django': (
    #     'https://docs.djangoproject.com/en/5.1/',
    #     'https://docs.djangoproject.com/en/5.1/_objects.inv',
    # ),
    # 'getpaid-core': ('https://getpaid-core.readthedocs.io/en/latest/', None),
}

# Suppress duplicate label warnings from autosectionlabel
# and intersphinx connection failures (work fine on ReadTheDocs)
suppress_warnings = ['autosectionlabel.*', 'intersphinx.external']
