import asyncio
import functools
import json
import threading

from django.test import RequestFactory

from getpaid import runtime
from getpaid.adapters import call_processor_verify_callback


async def _current_thread_id() -> int:
    await asyncio.sleep(0)
    return threading.get_ident()


def test_call_processor_method_reuses_one_async_thread() -> None:
    first_thread_id = runtime._call_processor_method(_current_thread_id)
    second_thread_id = runtime._call_processor_method(_current_thread_id)

    assert first_thread_id != threading.get_ident()
    assert second_thread_id == first_thread_id


def test_call_processor_verify_callback_reuses_one_async_thread() -> None:
    thread_ids: list[int] = []

    class Processor:
        async def verify_callback(self, data, headers, **kwargs) -> None:
            thread_ids.append(threading.get_ident())

    request = RequestFactory().post(
        '/callback/',
        data=json.dumps({'paymentId': 'P-1'}),
        content_type='application/json',
    )

    call_processor_verify_callback(Processor(), request)
    call_processor_verify_callback(Processor(), request)

    assert len(thread_ids) == 2
    assert thread_ids[0] != threading.get_ident()
    assert thread_ids[1] == thread_ids[0]


def test_call_processor_method_handles_decorated_async_callable() -> None:
    def async_wrapper(method):
        @functools.wraps(method)
        def wrapper(*args, **kwargs):
            return method(*args, **kwargs)

        return wrapper

    class Processor:
        @async_wrapper
        async def verify_callback(self) -> int:
            await asyncio.sleep(0)
            return threading.get_ident()

    result = runtime._call_processor_method(Processor().verify_callback)

    assert isinstance(result, int)
    assert result != threading.get_ident()
