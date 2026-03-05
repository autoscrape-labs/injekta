from collections.abc import AsyncGenerator, Generator

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


class TestInjectYieldSync:
    def test_yield_dependency_returns_value(self) -> None:
        def get_db() -> Generator[str]:
            yield 'db_connection'

        @inject
        def handler(db: str = Needs(get_db)) -> str:
            return db

        assert handler() == 'db_connection'

    def test_yield_dependency_runs_cleanup(self) -> None:
        events: list[str] = []

        def get_db() -> Generator[str]:
            events.append('setup')
            yield 'db'
            events.append('teardown')

        @inject
        def handler(db: str = Needs(get_db)) -> str:
            events.append('handler')
            return db

        handler()

        assert events == ['setup', 'handler', 'teardown']

    def test_yield_cleanup_runs_on_exception(self) -> None:
        cleanup_called = False

        def get_db() -> Generator[str]:
            nonlocal cleanup_called
            yield 'db'
            cleanup_called = True

        @inject
        def handler(db: str = Needs(get_db)) -> None:
            raise ValueError('boom')

        with pytest.raises(ValueError, match='boom'):
            handler()

        assert cleanup_called

    def test_mixed_yield_and_regular_dependencies(self) -> None:
        def get_config() -> dict[str, bool]:
            return {'debug': True}

        cleanup_called = False

        def get_db() -> Generator[str]:
            nonlocal cleanup_called
            yield 'db'
            cleanup_called = True

        @inject
        def handler(
            config: dict[str, bool] = Needs(get_config),
            db: str = Needs(get_db),
        ) -> tuple[dict[str, bool], str]:
            return config, db

        result = handler()

        assert result == ({'debug': True}, 'db')
        assert cleanup_called


    def test_teardown_runs_in_reverse_order(self) -> None:
        events: list[str] = []

        def get_a() -> Generator[str]:
            events.append('setup_a')
            yield 'a'
            events.append('teardown_a')

        def get_b() -> Generator[str]:
            events.append('setup_b')
            yield 'b'
            events.append('teardown_b')

        @inject
        def handler(a: str = Needs(get_a), b: str = Needs(get_b)) -> str:
            events.append('handler')
            return f'{a}+{b}'

        result = handler()

        assert result == 'a+b'
        assert events == ['setup_a', 'setup_b', 'handler', 'teardown_b', 'teardown_a']

    def test_diamond_yield_dependency_runs_once(self) -> None:
        call_count = 0
        cleanup_count = 0

        def get_config() -> Generator[dict[str, bool]]:
            nonlocal call_count, cleanup_count
            call_count += 1
            yield {'debug': True}
            cleanup_count += 1

        def get_db(config: dict[str, bool] = Needs(get_config)) -> str:
            return 'db'

        def get_auth(config: dict[str, bool] = Needs(get_config)) -> str:
            return 'auth'

        @inject
        def handler(db: str = Needs(get_db), auth: str = Needs(get_auth)) -> tuple[str, str]:
            return db, auth

        result = handler()

        assert result == ('db', 'auth')
        assert call_count == 1
        assert cleanup_count == 1


class TestInjectYieldAsync:
    @pytest.mark.asyncio
    async def test_async_yield_dependency(self) -> None:
        events: list[str] = []

        async def get_db() -> AsyncGenerator[str]:
            events.append('setup')
            yield 'async_db'
            events.append('teardown')

        @inject
        async def handler(db: str = Needs(get_db)) -> str:
            events.append('handler')
            return db

        result = await handler()

        assert result == 'async_db'
        assert events == ['setup', 'handler', 'teardown']

    @pytest.mark.asyncio
    async def test_async_yield_cleanup_runs_on_exception(self) -> None:
        cleanup_called = False

        async def get_db() -> AsyncGenerator[str]:
            nonlocal cleanup_called
            yield 'db'
            cleanup_called = True

        @inject
        async def handler(db: str = Needs(get_db)) -> None:
            raise ValueError('boom')

        with pytest.raises(ValueError, match='boom'):
            await handler()

        assert cleanup_called

