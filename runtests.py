#!/usr/bin/env python
# -*- coding: utf-8
from __future__ import absolute_import, unicode_literals

import os
import sys

import django
from django.conf import settings
from django.test.utils import get_runner


def run_tests(*test_args):
    if not test_args:
        test_args = ["tests"]

    os.environ["DJANGO_SETTINGS_MODULE"] = "tests.settings"
    django.setup()
    TestRunner = get_runner(settings)
    test_runner = TestRunner()
    failures = test_runner.run_tests(test_args)
    sys.exit(bool(failures))


def run_swapped_tests(*test_args):
    if not test_args:
        test_args = ["tests"]

    os.environ["DJANGO_SETTINGS_MODULE"] = "tests.settings_swapped"
    django.setup()
    TestRunner = get_runner(settings)
    test_runner = TestRunner()
    failures = test_runner.run_tests(test_args)
    sys.exit(bool(failures))


if __name__ == "__main__":
    run_tests(*sys.argv[1:])
    run_swapped_tests(*sys.argv[1:])
