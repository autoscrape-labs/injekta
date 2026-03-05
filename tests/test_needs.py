from injecta.core.needs import Needs


def _dummy_dependency() -> str:
    return 'value'


class TestNeedsInit:
    def test_stores_dependency_callable(self) -> None:
        needs = Needs(_dummy_dependency)

        assert needs.dependency is _dummy_dependency


class TestNeedsRepr:
    def test_repr_shows_function_name(self) -> None:
        needs = Needs(_dummy_dependency)

        assert repr(needs) == 'Needs(_dummy_dependency)'

    def test_repr_with_callable_without_name(self) -> None:
        callable_obj = type('Anon', (), {'__call__': lambda self: None})()
        needs = Needs(callable_obj)

        assert 'Needs(' in repr(needs)
