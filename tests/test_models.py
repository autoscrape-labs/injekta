from injecta.core.models import Dependant


def _provider() -> str:
    return 'value'


def _sub_provider() -> int:
    return 42


class TestDependant:
    def test_creates_with_callable(self) -> None:
        dep = Dependant(call=_provider)

        assert dep.call is _provider
        assert dep.dependencies == []
        assert dep.param_name == ''

    def test_stores_sub_dependencies(self) -> None:
        sub = Dependant(call=_sub_provider, param_name='count')
        parent = Dependant(call=_provider, dependencies=[sub])

        assert len(parent.dependencies) == 1
        assert parent.dependencies[0].call is _sub_provider

    def test_custom_param_name(self) -> None:
        dep = Dependant(call=_provider, param_name='config')

        assert dep.param_name == 'config'
