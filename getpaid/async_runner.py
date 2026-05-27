"""Run async processor methods from Django's synchronous adapter layer."""

from __future__ import annotations

import asyncio
import atexit
import threading
from collections.abc import Awaitable
from typing import TypeVar

_Result = TypeVar('_Result')


class AsyncRunner:
    """Run awaitables on a dedicated event loop thread.

    django-getpaid's public API is synchronous, but core processors are async.
    Using ``asgiref.async_to_sync()`` here creates a fresh event loop thread
    for each call. A shared runner keeps one long-lived loop thread instead,
    avoiding per-call thread churn at the Django adapter boundary.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._ready = threading.Event()
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    def run(self, awaitable: Awaitable[_Result]) -> _Result:
        self._ensure_started()
        loop = self._loop
        thread = self._thread
        if loop is None or thread is None:
            raise RuntimeError('Async runner failed to start.')
        if threading.get_ident() == thread.ident:
            raise RuntimeError('Async runner cannot block on its own loop thread.')
        future = asyncio.run_coroutine_threadsafe(awaitable, loop)
        return future.result()

    def shutdown(self) -> None:
        with self._lock:
            loop = self._loop
            thread = self._thread
            if loop is None or thread is None:
                return
            loop.call_soon_threadsafe(loop.stop)
            thread.join(timeout=1)
            self._loop = None
            self._thread = None
            self._ready.clear()

    def _ensure_started(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._ready.clear()
            self._thread = threading.Thread(
                target=self._run_loop,
                name='getpaid-async-runner',
                daemon=True,
            )
            self._thread.start()
        self._ready.wait()

    def _run_loop(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        self._ready.set()
        try:
            loop.run_forever()
        finally:
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(
                    asyncio.gather(*pending, return_exceptions=True)
                )
            loop.close()


_runner = AsyncRunner()
atexit.register(_runner.shutdown)


def run_awaitable[AwaitedResult](
    awaitable: Awaitable[AwaitedResult],
) -> AwaitedResult:
    """Block synchronously until an awaitable completes."""
    return _runner.run(awaitable)
