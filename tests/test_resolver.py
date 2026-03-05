import pytest

from injecta.core.needs import Needs
from injecta.exceptions import ResolutionError
from injecta.resolution.resolver import resolve_dependencies


def _get_db() -> dict[str, str]:
    return {'connection': 'db'}


def _get_config() -> dict[str, bool]:
    return {'debug': True}


def _get_service(db: dict[str, str] = Needs(_get_db)) -> dict[str, str]:
    return {'service': 'api', **db}


class TestResolveDependencies:
    def test_function_without_dependencies(self) -> None:
        def no_deps() -> str:
            return 'value'

        dependant = resolve_dependencies(no_deps)

        assert dependant.call is no_deps
        assert dependant.dependencies == []

    def test_function_with_single_dependency(self) -> None:
        def handler(db: dict[str, str] = Needs(_get_db)) -> None: ...

        dependant = resolve_dependencies(handler)

        assert len(dependant.dependencies) == 1
        assert dependant.dependencies[0].call is _get_db
        assert dependant.dependencies[0].param_name == 'db'

    def test_function_with_multiple_dependencies(self) -> None:
        def handler(
            db: dict[str, str] = Needs(_get_db),
            config: dict[str, bool] = Needs(_get_config),
        ) -> None: ...

        dependant = resolve_dependencies(handler)

        assert len(dependant.dependencies) == 2
        assert dependant.dependencies[0].param_name == 'db'
        assert dependant.dependencies[1].param_name == 'config'

    def test_nested_dependencies(self) -> None:
        def handler(service: dict[str, str] = Needs(_get_service)) -> None: ...

        dependant = resolve_dependencies(handler)

        assert len(dependant.dependencies) == 1
        service_dep = dependant.dependencies[0]
        assert service_dep.call is _get_service
        assert len(service_dep.dependencies) == 1
        assert service_dep.dependencies[0].call is _get_db

    def test_skips_regular_parameters(self) -> None:
        def handler(
            db: dict[str, str] = Needs(_get_db),
            skip: int = 0,
        ) -> None: ...

        dependant = resolve_dependencies(handler)

        assert len(dependant.dependencies) == 1
        assert dependant.dependencies[0].param_name == 'db'

    def test_detects_circular_dependency(self) -> None:
        def dep_a(b: str = Needs(lambda: '')) -> str:  # noqa: E731
            return b

        def dep_b(a: str = Needs(dep_a)) -> str:
            return a

        dep_a.__defaults__ = (Needs(dep_b),)

        with pytest.raises(ResolutionError, match='Circular dependency'):
            resolve_dependencies(dep_a)

    def test_allows_diamond_dependency(self) -> None:
        def shared() -> str:
            return 'shared'

        def branch_a(s: str = Needs(shared)) -> str:
            return s

        def branch_b(s: str = Needs(shared)) -> str:
            return s

        def handler(
            a: str = Needs(branch_a),
            b: str = Needs(branch_b),
        ) -> None: ...

        dependant = resolve_dependencies(handler)

        assert len(dependant.dependencies) == 2
        assert dependant.dependencies[0].dependencies[0].call is shared
        assert dependant.dependencies[1].dependencies[0].call is shared
