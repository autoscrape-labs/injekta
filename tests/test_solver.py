import pytest

from injecta.core.models import Dependant
from injecta.core.needs import Needs
from injecta.exceptions import InjectionError
from injecta.resolution.resolver import resolve_dependencies
from injecta.resolution.solver import solve_dependencies, solve_dependencies_sync


def _get_config() -> dict[str, bool]:
    return {'debug': True}


def _get_db() -> dict[str, str]:
    return {'connection': 'db'}


def _get_service(db: dict[str, str] = Needs(_get_db)) -> dict[str, str]:
    return {'service': 'api', **db}


async def _get_async_db() -> dict[str, str]:
    return {'connection': 'async_db'}


class TestSolveDependenciesAsync:
    @pytest.mark.asyncio
    async def test_resolves_single_sync_dependency(self) -> None:
        def handler(config: dict[str, bool] = Needs(_get_config)) -> None: ...

        dependant = resolve_dependencies(handler)
        values = await solve_dependencies(dependant)

        assert values == {'config': {'debug': True}}

    @pytest.mark.asyncio
    async def test_resolves_single_async_dependency(self) -> None:
        def handler(db: dict[str, str] = Needs(_get_async_db)) -> None: ...

        dependant = resolve_dependencies(handler)
        values = await solve_dependencies(dependant)

        assert values == {'db': {'connection': 'async_db'}}

    @pytest.mark.asyncio
    async def test_resolves_nested_dependencies(self) -> None:
        def handler(service: dict[str, str] = Needs(_get_service)) -> None: ...

        dependant = resolve_dependencies(handler)
        values = await solve_dependencies(dependant)

        assert values == {'service': {'service': 'api', 'connection': 'db'}}

    @pytest.mark.asyncio
    async def test_no_dependencies_returns_empty(self) -> None:
        dependant = Dependant(call=lambda: None)
        values = await solve_dependencies(dependant)

        assert values == {}


class TestSolveDependenciesSync:
    def test_resolves_sync_dependency(self) -> None:
        def handler(config: dict[str, bool] = Needs(_get_config)) -> None: ...

        dependant = resolve_dependencies(handler)
        values = solve_dependencies_sync(dependant)

        assert values == {'config': {'debug': True}}

    def test_resolves_nested_sync_dependencies(self) -> None:
        def handler(service: dict[str, str] = Needs(_get_service)) -> None: ...

        dependant = resolve_dependencies(handler)
        values = solve_dependencies_sync(dependant)

        assert values == {'service': {'service': 'api', 'connection': 'db'}}

    def test_raises_on_async_dependency(self) -> None:
        def handler(db: dict[str, str] = Needs(_get_async_db)) -> None: ...

        dependant = resolve_dependencies(handler)

        with pytest.raises(InjectionError, match='async dependency.*sync context'):
            solve_dependencies_sync(dependant)
