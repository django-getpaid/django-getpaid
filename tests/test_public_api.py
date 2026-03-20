"""Tests for the public package API."""

import getpaid


def test_version() -> None:
    assert getpaid.__version__ == '3.0.0a3'
