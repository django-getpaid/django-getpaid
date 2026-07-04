"""ProcessorBridge: single seam for calling processor methods across the
Django sync / core async boundary.

Consolidates three scattered async-detection + run_awaitable patterns:

1. abstracts.py:_call_processor_method — generic async/sync call
2. adapters.py:call_processor_verify_callback — verify_callback with
   Django-style (sync, takes request) fallback
3. views.py:_uses_semantic_callback — identity check to determine whether
   a processor implements the core async handle_callback contract

All delegate to ProcessorBridge, which owns:

- Async detection (via getpaid.async_detection.is_async_callable)
- Runner invocation (via getpaid.async_runner.run_awaitable)
- Semantic callback identification (MRO walk instead of fragile identity check)
"""

from __future__ import annotations

from typing import Any

from getpaid.async_runner import run_awaitable


class ProcessorBridge:
    """Call processor methods, bridging Django sync ↔ core async.

    Usage::

        bridge = ProcessorBridge()
        result = bridge.call(processor, 'prepare_transaction', request=request)
    """

    def call(
        self, processor: Any, method: Any, *args: Any, **kwargs: Any,
    ) -> Any:
        """Call a processor method, routing through the async runner if needed.

        :param processor: The processor instance (used for is_async_callable
            detection on bound methods).
        :param method: The bound method or callable to invoke.
        :return: The method's return value.
        """
        from getpaid.async_detection import is_async_callable

        if is_async_callable(method):
            return run_awaitable(method(*args, **kwargs))
        return method(*args, **kwargs)

    def is_semantic_callback(self, processor: Any) -> bool:
        """Return True when the processor implements the core async callback
        contract (async ``handle_callback(data, headers, **kwargs)``).

        Uses an MRO walk instead of the old fragile identity check
        (``type(processor).handle_callback is not CoreBaseProcessor.handle_callback``),
        which broke when a backend inherited from an intermediate Django processor.

        Walks the processor's MRO and returns True if the first class that
        defines ``handle_callback`` in its own ``__dict__`` has an async
        definition. Falls back to checking the instance's own ``__dict__``
        (needed for test mocks that set methods on the instance, not the class).
        """
        from getpaid.async_detection import is_async_callable

        for cls in type(processor).__mro__:
            if 'handle_callback' in cls.__dict__:
                handle = cls.__dict__['handle_callback']
                return is_async_callable(handle)
        # Fallback: check instance __dict__ (handles test mocks)
        if 'handle_callback' in getattr(processor, '__dict__', {}):
            return is_async_callable(processor.__dict__['handle_callback'])
        return False

    def call_verify_callback(
        self, processor: Any, data: Any, headers: Any, raw_body: Any,
        request: Any, **kwargs: Any,
    ) -> None:
        """Call processor.verify_callback, handling both sync and async styles.

        Core-style (async): ``verify_callback(data, headers, raw_body=...)``
        Django-style (sync): ``verify_callback(request)``

        :param processor: The processor instance.
        :param data: Parsed callback payload.
        :param headers: Normalized HTTP headers.
        :param raw_body: Raw HTTP body bytes.
        :param request: The original Django HttpRequest (for sync fallback).
        """
        from getpaid.async_detection import is_async_callable

        verify_method = getattr(processor, 'verify_callback', None)
        if verify_method is None:
            return

        if is_async_callable(verify_method):
            run_awaitable(
                verify_method(data, headers, raw_body=raw_body, **kwargs),
            )
        else:
            verify_method(request)


#: Module-level singleton — stateless, safe to reuse.
bridge = ProcessorBridge()
