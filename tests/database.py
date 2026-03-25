"""Shared test database settings helpers."""

from __future__ import annotations

import os
from urllib.parse import urlparse


def get_test_databases() -> dict[str, dict[str, object]]:
    database_url = os.environ.get('TEST_DATABASE_URL')
    if not database_url:
        return {
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': ':memory:',
            }
        }

    parsed = urlparse(database_url)
    engine = _django_engine(parsed.scheme)
    return {
        'default': {
            'ENGINE': engine,
            'NAME': parsed.path.lstrip('/'),
            'USER': parsed.username or '',
            'PASSWORD': parsed.password or '',
            'HOST': parsed.hostname or '',
            'PORT': parsed.port or '',
        }
    }


def _django_engine(scheme: str) -> str:
    normalized = scheme.lower()
    if normalized in {'postgres', 'postgresql'}:
        return 'django.db.backends.postgresql'
    raise ValueError(f'Unsupported TEST_DATABASE_URL scheme: {scheme}')
