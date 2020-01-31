#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import re
import sys

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup


def get_version(*file_paths):
    """Retrieves the version from getpaid/__init__.py"""
    filename = os.path.join(os.path.dirname(__file__), *file_paths)
    version_file = open(filename).read()
    version_match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]",
                              version_file, re.M)
    if version_match:
        return version_match.group(1)
    raise RuntimeError('Unable to find version string.')


version = get_version("getpaid", "__init__.py")

if sys.argv[-1] == 'publish':
    try:
        import wheel

        print("Wheel version: ", wheel.__version__)
    except ImportError:
        print('Wheel library missing. Please run "pip install wheel"')
        sys.exit()
    os.system('python setup.py sdist upload')
    os.system('python setup.py bdist_wheel upload')
    sys.exit()

if sys.argv[-1] == 'tag':
    print("Tagging the version on git:")
    os.system("git tag -a %s -m 'version %s'" % (version, version))
    os.system("git push --tags")
    sys.exit()

readme = open('README.rst').read()
history = open('HISTORY.rst').read().replace('.. :changelog:', '')

setup(
    name='django-getpaid',
    version=version,
    description="""Multi-broker payment processor for Django""",
    long_description=readme + '\n\n' + history,
    author='Django-getpaid Team',
    author_email='d.kozaczko@sunscrapers.com',
    url='https://github.com/django-getpaid/django-getpaid',
    packages=[
        'getpaid',
    ],
    include_package_data=True,
    install_requires=["django-model-utils>=2.0", ],
    license="MIT",
    zip_safe=False,
    keywords='django-getpaid',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Framework :: Django :: 1.11',
        'Framework :: Django :: 2.0',
        'Framework :: Django :: 2.2',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Natural Language :: English',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ],
    extras_require={
        'payu': [
            'django-celery>=3.0.11',
        ],
        # 'przelewy24': [
        #     'django-celery>=3.0.11',
        #     'pytz',
        # ],
        # 'moip': [
        #     'requests',
        #     'lxml'
        # ],
        # 'paymill': [
        #     'pymill',
        # ]
    },

)
