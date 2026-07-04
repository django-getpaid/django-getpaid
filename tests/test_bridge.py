"""Tests for ProcessorBridge — the single async/sync call seam."""

from unittest.mock import AsyncMock, Mock, patch

from getpaid.bridge import ProcessorBridge


class TestBridgeCall:
    """ProcessorBridge.call routes sync methods directly and async methods
    through run_awaitable."""

    def test_call_sync_method(self):
        """A sync method is called directly, return value passed through."""
        bridge = ProcessorBridge()
        method = Mock(return_value='sync_result')

        result = bridge.call(Mock(), method, 'arg1', key='val')

        method.assert_called_once_with('arg1', key='val')
        assert result == 'sync_result'

    def test_call_async_method(self):
        """An async method is run via run_awaitable."""
        bridge = ProcessorBridge()
        method = AsyncMock(return_value='async_result')

        with patch('getpaid.bridge.run_awaitable', return_value='bridged') as mock_run:
            result = bridge.call(Mock(), method, 'arg1')

        # The async method is NOT called directly — run_awaitable handles it
        method.assert_called_once_with('arg1')
        mock_run.assert_called_once()
        assert result == 'bridged'

    def test_call_passes_all_args(self):
        """All positional and keyword args are forwarded."""
        bridge = ProcessorBridge()
        method = Mock(return_value=None)

        bridge.call(Mock(), method, 1, 2, 3, a='x', b='y')

        method.assert_called_once_with(1, 2, 3, a='x', b='y')


class TestBridgeIsSemanticCallback:
    """ProcessorBridge.is_semantic_callback detects whether a processor
    implements the core async handle_callback contract."""

    def test_returns_true_for_core_async_processor(self):
        """A processor with async handle_callback returns True."""
        bridge = ProcessorBridge()

        class CoreProcessor:
            async def handle_callback(self, data, headers, **kwargs):
                pass

        assert bridge.is_semantic_callback(CoreProcessor()) is True

    def test_returns_false_for_sync_processor(self):
        """A processor with sync handle_callback returns False."""
        bridge = ProcessorBridge()

        class SyncProcessor:
            def handle_callback(self, data, headers, **kwargs):
                pass

        assert bridge.is_semantic_callback(SyncProcessor()) is False

    def test_returns_false_when_no_handle_callback(self):
        """A processor without handle_callback returns False."""
        bridge = ProcessorBridge()

        class NoCallbackProcessor:
            pass

        assert bridge.is_semantic_callback(NoCallbackProcessor()) is False

    def test_mro_walk_finds_first_definition(self):
        """The MRO walk finds the first class that defines handle_callback
        in its own __dict__, not inherited ones."""
        bridge = ProcessorBridge()

        class Base:
            async def handle_callback(self, data, headers, **kwargs):
                pass

        class Child(Base):
            pass  # Inherits async handle_callback from Base

        # Child doesn't define handle_callback, so the walk finds Base's
        assert bridge.is_semantic_callback(Child()) is True

    def test_mro_walk_stops_at_first_definer(self):
        """If an intermediate class overrides with sync, the walk stops there
        even if the base has async."""
        bridge = ProcessorBridge()

        class Base:
            async def handle_callback(self, data, headers, **kwargs):
                pass

        class Middle(Base):
            def handle_callback(self, data, headers, **kwargs):
                pass  # Sync override

        class Child(Middle):
            pass

        # Middle defines handle_callback (sync), so the walk stops there
        assert bridge.is_semantic_callback(Child()) is False

    def test_handles_wrapped_async_method(self):
        """A decorated async method (e.g. with functools.wraps) is detected."""
        bridge = ProcessorBridge()

        def async_decorator(fn):
            @functools.wraps(fn)
            async def wrapper(*args, **kwargs):
                return await fn(*args, **kwargs)
            return wrapper

        import functools

        class WrappedProcessor:
            @async_decorator
            async def handle_callback(self, data, headers, **kwargs):
                pass

        assert bridge.is_semantic_callback(WrappedProcessor()) is True


class TestBridgeCallVerifyCallback:
    """ProcessorBridge.call_verify_callback handles both sync and async
    verify_callback styles."""

    def test_async_verify_callback(self):
        """Core-style async verify_callback is called with data, headers, raw_body."""
        bridge = ProcessorBridge()
        processor = Mock()
        processor.verify_callback = AsyncMock()

        data = {'status': 'ok'}
        headers = {'Signature': 'abc'}
        raw_body = b'{"status": "ok"}'
        request = Mock()

        with patch('getpaid.bridge.run_awaitable') as mock_run:
            bridge.call_verify_callback(
                processor, data, headers, raw_body, request,
            )

        processor.verify_callback.assert_called_once_with(
            data, headers, raw_body=raw_body,
        )
        mock_run.assert_called_once()

    def test_sync_verify_callback(self):
        """Django-style sync verify_callback is called with request."""
        bridge = ProcessorBridge()
        processor = Mock()
        processor.verify_callback = Mock()  # Sync

        data = {'status': 'ok'}
        headers = {}
        raw_body = b''
        request = Mock()

        bridge.call_verify_callback(
            processor, data, headers, raw_body, request,
        )

        processor.verify_callback.assert_called_once_with(request)

    def test_no_verify_callback(self):
        """When processor has no verify_callback, nothing happens."""
        bridge = ProcessorBridge()
        processor = Mock(spec=[])  # No verify_callback attribute

        # Should not raise
        bridge.call_verify_callback(
            processor, {}, {}, b'', Mock(),
        )

    def test_async_verify_with_extra_kwargs(self):
        """Extra kwargs are passed through to async verify_callback."""
        bridge = ProcessorBridge()
        processor = Mock()
        processor.verify_callback = AsyncMock()

        with patch('getpaid.bridge.run_awaitable'):
            bridge.call_verify_callback(
                processor, {'a': 1}, {'h': 'v'}, b'body', Mock(),
                extra_kw='extra',
            )

        processor.verify_callback.assert_called_once_with(
            {'a': 1}, {'h': 'v'}, raw_body=b'body', extra_kw='extra',
        )


class TestBridgeSingleton:
    """The module-level bridge singleton is stateless and reusable."""

    def test_singleton_exists(self):
        from getpaid.bridge import bridge

        assert isinstance(bridge, ProcessorBridge)

    def test_singleton_is_reusable(self):
        from getpaid.bridge import bridge

        method = Mock(return_value='ok')
        result = bridge.call(Mock(), method)
        assert result == 'ok'
