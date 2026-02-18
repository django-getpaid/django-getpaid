"""Adapters to bridge Django sync views to core async processors."""

import inspect
import json
from typing import Any

from asgiref.sync import async_to_sync
from django.http import HttpRequest


def adapt_callback_request(
    request: HttpRequest,
) -> tuple[dict[str, Any], dict[str, str], bytes]:
    """Extract (data, headers, raw_body) from Django HttpRequest.

    Returns:
        (data, headers, raw_body) tuple suitable for core processor.verify_callback()
    """
    # Capture raw_body first before accessing POST (which consumes the stream)
    raw_body = request.body

    # Extract data from request body
    if request.content_type and 'json' in request.content_type:
        data = json.loads(raw_body)
    else:
        data = dict(request.POST)

    # Extract headers (HTTP_X_FOO → X-Foo)
    headers = {
        key.replace('HTTP_', '', 1).replace('_', '-'): value
        for key, value in request.META.items()
        if key.startswith('HTTP_')
    }

    return data, headers, raw_body


def call_processor_verify_callback(
    processor: Any, request: HttpRequest
) -> None:
    """Call processor.verify_callback, handling async/sync bridge.

    Detects if processor has async verify_callback and uses async_to_sync if needed.
    Falls back to Django-style verify_callback(request) for backward compat.
    """
    verify_method = getattr(processor, 'verify_callback', None)

    if verify_method is None:
        return  # No verification needed

    # Check if it's an async method
    if inspect.iscoroutinefunction(verify_method):
        # Core-style: async def verify_callback(data, headers, **kwargs)
        data, headers, raw_body = adapt_callback_request(request)
        async_to_sync(verify_method)(data, headers, raw_body=raw_body)
    else:
        # Django-style (backward compat): def verify_callback(request)
        verify_method(request)
