from getpaid.utils import update


class TestUpdate:
    """Tests for the recursive dict update utility."""

    def test_simple_update(self):
        d = {'a': 1, 'b': 2}
        result = update(d, {'b': 3, 'c': 4})
        assert result == {'a': 1, 'b': 3, 'c': 4}
        # Should mutate in-place and return the same dict
        assert result is d

    def test_nested_update(self):
        d = {'a': {'x': 1, 'y': 2}, 'b': 3}
        result = update(d, {'a': {'y': 99, 'z': 100}})
        assert result == {'a': {'x': 1, 'y': 99, 'z': 100}, 'b': 3}

    def test_deep_nested_update(self):
        d = {'a': {'b': {'c': 1}}}
        result = update(d, {'a': {'b': {'d': 2}}})
        assert result == {'a': {'b': {'c': 1, 'd': 2}}}

    def test_overwrite_scalar_with_dict(self):
        d = {'a': 1}
        result = update(d, {'a': {'nested': True}})
        assert result == {'a': {'nested': True}}

    def test_overwrite_dict_with_scalar(self):
        d = {'a': {'nested': True}}
        result = update(d, {'a': 42})
        assert result == {'a': 42}

    def test_empty_update(self):
        d = {'a': 1}
        result = update(d, {})
        assert result == {'a': 1}

    def test_update_empty_dict(self):
        d = {}
        result = update(d, {'a': 1})
        assert result == {'a': 1}

    def test_both_empty(self):
        d = {}
        result = update(d, {})
        assert result == {}
