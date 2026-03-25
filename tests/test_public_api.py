"""Tests for the public package API."""

import tomllib
from pathlib import Path

import getpaid


def test_version() -> None:
    assert getpaid.__version__ == '3.0.0a4'


def test_core_dependency_floor() -> None:
    pyproject_data = tomllib.loads(Path('pyproject.toml').read_text())
    assert (
        'python-getpaid-core>=3.0.0a4'
        in pyproject_data['project']['dependencies']
    )
    assert (
        'python-getpaid-core>=3.0.0a4'
        in pyproject_data['dependency-groups']['dev']
    )
