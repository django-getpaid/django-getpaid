"""Tests for test database configuration helpers."""

import pytest


def test_database_settings_default_to_sqlite(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.database import get_test_databases

    monkeypatch.delenv('TEST_DATABASE_URL', raising=False)

    assert get_test_databases() == {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': ':memory:',
        }
    }


def test_database_settings_use_postgres_environment_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.database import get_test_databases

    monkeypatch.setenv(
        'TEST_DATABASE_URL',
        'postgres://test_user:test_password@testdb:5432/test_db',
    )

    assert get_test_databases() == {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': 'test_db',
            'USER': 'test_user',
            'PASSWORD': 'test_password',
            'HOST': 'testdb',
            'PORT': 5432,
        }
    }
