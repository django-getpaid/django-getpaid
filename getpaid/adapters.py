"""Adapters to bridge Django sync views to core async processors."""

import json
from typing import Any

from django.http import HttpRequest

from getpaid.bridge import bridge


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
        data = {}
        for key in request.POST:
            values = list(request.POST.getlist(key))
            data[key] = values[0] if len(values) == 1 else values

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

    Delegates to ProcessorBridge.call_verify_callback which handles:
    - Core-style (async): verify_callback(data, headers, raw_body=...)
    - Django-style (sync): verify_callback(request)
    """
    data, headers, raw_body = adapt_callback_request(request)
    bridge.call_verify_callback(
        processor, data, headers, raw_body, request,
    )
