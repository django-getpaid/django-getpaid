"""Tests for callback adapter."""

import json
from unittest.mock import AsyncMock, Mock

import pytest
from django.test import RequestFactory

from getpaid.adapters import (
    adapt_callback_request,
    call_processor_verify_callback,
)


@pytest.fixture
def factory():
    return RequestFactory()


def test_adapt_callback_request_json(factory):
    """Test JSON payload extraction."""
    payload = {'status': 'completed', 'transaction_id': '12345'}
    request = factory.post(
        '/callback/',
        data=json.dumps(payload),
        content_type='application/json',
        HTTP_X_SIGNATURE='abc123',
        HTTP_AUTHORIZATION='Bearer token',
    )

    data, headers, raw_body = adapt_callback_request(request)

    assert data == payload
    assert headers['X-SIGNATURE'] == 'abc123'
    assert headers['AUTHORIZATION'] == 'Bearer token'
    assert raw_body == request.body


def test_adapt_callback_request_form_data(factory):
    """Test form data extraction."""
    request = factory.post(
        '/callback/',
        data={'status': 'paid', 'amount': '100'},
        HTTP_X_CUSTOM='value',
    )

    data, headers, raw_body = adapt_callback_request(request)

    assert 'status' in data
    assert headers['X-CUSTOM'] == 'value'


def test_call_processor_verify_callback_async():
    """Test async processor verification."""
    processor = Mock()
    processor.verify_callback = AsyncMock()

    factory = RequestFactory()
    request = factory.post(
        '/callback/',
        data=json.dumps({'test': 'data'}),
        content_type='application/json',
    )

    call_processor_verify_callback(processor, request)

    # Should have been called with (data, headers, raw_body=...)
    processor.verify_callback.assert_called_once()
    call_args = processor.verify_callback.call_args
    assert call_args[0][0] == {'test': 'data'}  # data
    assert isinstance(call_args[0][1], dict)  # headers
    assert 'raw_body' in call_args[1]  # kwargs


def test_call_processor_verify_callback_sync():
    """Test sync processor verification (backward compat)."""
    processor = Mock()
    processor.verify_callback = Mock()  # Sync method

    factory = RequestFactory()
    request = factory.post('/callback/', data={'test': 'data'})

    call_processor_verify_callback(processor, request)

    # Should have been called with HttpRequest directly
    processor.verify_callback.assert_called_once_with(request)
