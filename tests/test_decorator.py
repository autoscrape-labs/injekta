import pytest

from injecta import Needs, inject
from injecta.exceptions import InjectionError


def _get_config() -> dict[str, bool]:
    return {'debug': True}


def _get_db() -> dict[str, str]:
    return {'connection': 'db'}


def _get_service(db: dict[str, str] = Needs(_get_db)) -> dict[str, str]:
    return {'service': 'api', **db}


async def _get_async_db() -> dict[str, str]:
    return {'connection': 'async_db'}


class TestInjectSync:
    def test_injects_single_dependency(self) -> None:
        @inject
        def handler(config: dict[str, bool] = Needs(_get_config)) -> dict[str, bool]:
            return config

        result = handler()

        assert result == {'debug': True}

    def test_injects_nested_dependencies(self) -> None:
        @inject
        def handler(service: dict[str, str] = Needs(_get_service)) -> dict[str, str]:
            return service

        result = handler()

        assert result == {'service': 'api', 'connection': 'db'}

    def test_explicit_kwargs_override_injection(self) -> None:
        @inject
        def handler(config: dict[str, bool] = Needs(_get_config)) -> dict[str, bool]:
            return config

        custom = {'debug': False, 'custom': True}
        result = handler(config=custom)

        assert result == custom

    def test_preserves_regular_parameters(self) -> None:
        @inject
        def handler(
            config: dict[str, bool] = Needs(_get_config),
            skip: int = 0,
        ) -> tuple[dict[str, bool], int]:
            return config, skip

        result = handler(skip=10)

        assert result == ({'debug': True}, 10)

    def test_raises_on_async_dependency_in_sync(self) -> None:
        @inject
        def handler(db: dict[str, str] = Needs(_get_async_db)) -> dict[str, str]:
            return db

        with pytest.raises(InjectionError):
            handler()


class TestInjectAsync:
    @pytest.mark.asyncio
    async def test_injects_async_dependency(self) -> None:
        @inject
        async def handler(db: dict[str, str] = Needs(_get_async_db)) -> dict[str, str]:
            return db

        result = await handler()

        assert result == {'connection': 'async_db'}

    @pytest.mark.asyncio
    async def test_injects_sync_dependency_in_async(self) -> None:
        @inject
        async def handler(config: dict[str, bool] = Needs(_get_config)) -> dict[str, bool]:
            return config

        result = await handler()

        assert result == {'debug': True}

    @pytest.mark.asyncio
    async def test_injects_nested_dependencies(self) -> None:
        @inject
        async def handler(service: dict[str, str] = Needs(_get_service)) -> dict[str, str]:
            return service

        result = await handler()

        assert result == {'service': 'api', 'connection': 'db'}

    @pytest.mark.asyncio
    async def test_explicit_kwargs_override_injection(self) -> None:
        @inject
        async def handler(db: dict[str, str] = Needs(_get_async_db)) -> dict[str, str]:
            return db

        custom = {'connection': 'custom'}
        result = await handler(db=custom)

        assert result == custom


