import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Annotated, Protocol

import pytest

from injekta import Container, Needs, inject
from injekta.exceptions import InjectionError


class Database(Protocol):
    def query(self, sql: str) -> list[dict[str, str]]: ...


class Logger(Protocol):
    def info(self, msg: str) -> None: ...


class FakeDB:
    def query(self, sql: str) -> list[dict[str, str]]:
        return [{'sql': sql}]


class FakeLogger:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def info(self, msg: str) -> None:
        self.messages.append(msg)


class TestContainerRegister:
    def test_register_instance_as_singleton(self) -> None:
        container = Container()
        db = FakeDB()
        container.register(Database, db)

        assert container.resolve(Database) is db

    def test_register_class_as_factory(self) -> None:
        container = Container()
        container.register(Database, FakeDB)

        first = container.resolve(Database)
        second = container.resolve(Database)

        assert isinstance(first, FakeDB)
        assert isinstance(second, FakeDB)
        assert first is not second

    def test_register_lambda_as_factory(self) -> None:
        container = Container()
        container.register(Database, lambda: FakeDB())

        first = container.resolve(Database)
        second = container.resolve(Database)

        assert isinstance(first, FakeDB)
        assert isinstance(second, FakeDB)
        assert first is not second

    def test_register_function_as_factory(self) -> None:
        container = Container()

        def make_db() -> FakeDB:
            return FakeDB()

        container.register(Database, make_db)

        first = container.resolve(Database)
        second = container.resolve(Database)

        assert isinstance(first, FakeDB)
        assert isinstance(second, FakeDB)
        assert first is not second


class TestContainerResolve:
    def test_raises_on_unregistered_type(self) -> None:
        container = Container()

        with pytest.raises(InjectionError, match="No registration found for 'Database'"):
            container.resolve(Database)

    def test_singleton_returns_same_instance(self) -> None:
        container = Container()
        db = FakeDB()
        container.register(Database, db)

        assert container.resolve(Database) is container.resolve(Database)


class TestContainerNeeds:
    def test_returns_needs_marker(self) -> None:
        container = Container()
        container.register(Database, FakeDB())

        needs = container.Needs(Database)

        assert isinstance(needs, Needs)

    def test_needs_resolves_from_container(self) -> None:
        container = Container()
        db = FakeDB()
        container.register(Database, db)

        needs = container.Needs(Database)
        result = needs.dependency()

        assert result is db


class TestContainerOverride:
    def test_override_replaces_singleton(self) -> None:
        container = Container()
        original_db = FakeDB()
        override_db = FakeDB()
        container.register(Database, original_db)

        with container.override(Database, override_db):
            assert container.resolve(Database) is override_db

        assert container.resolve(Database) is original_db

    def test_override_replaces_factory(self) -> None:
        container = Container()
        container.register(Database, FakeDB)
        override_db = FakeDB()

        with container.override(Database, override_db):
            assert container.resolve(Database) is override_db

        result = container.resolve(Database)
        assert isinstance(result, FakeDB)
        assert result is not override_db

    def test_override_with_factory_over_singleton(self) -> None:
        container = Container()
        original_db = FakeDB()
        container.register(Database, original_db)

        with container.override(Database, FakeDB):
            first = container.resolve(Database)
            second = container.resolve(Database)
            assert first is not second

        assert container.resolve(Database) is original_db

    def test_override_restores_on_exception(self) -> None:
        container = Container()
        original_db = FakeDB()
        container.register(Database, original_db)

        with pytest.raises(RuntimeError):
            with container.override(Database, FakeDB()):
                raise RuntimeError('boom')

        assert container.resolve(Database) is original_db

    def test_nested_overrides(self) -> None:
        container = Container()
        db_a = FakeDB()
        db_b = FakeDB()
        db_c = FakeDB()
        container.register(Database, db_a)

        with container.override(Database, db_b):
            assert container.resolve(Database) is db_b

            with container.override(Database, db_c):
                assert container.resolve(Database) is db_c

            assert container.resolve(Database) is db_b

        assert container.resolve(Database) is db_a

    def test_override_works_with_inject(self) -> None:
        container = Container()
        container.register(Database, FakeDB())
        override_db = FakeDB()

        @inject
        def handler(db: Annotated[Database, container.Needs(Database)]) -> object:
            return db

        with container.override(Database, override_db):
            assert handler() is override_db


class TestContainerInjectSync:
    def test_injects_registered_type(self) -> None:
        container = Container()
        container.register(Database, FakeDB())

        @inject
        def handler(db: Annotated[Database, container.Needs(Database)]) -> list[dict[str, str]]:
            return db.query('SELECT 1')

        assert handler() == [{'sql': 'SELECT 1'}]

    def test_injects_multiple_types(self) -> None:
        container = Container()
        db = FakeDB()
        logger = FakeLogger()
        container.register(Database, db)
        container.register(Logger, logger)

        @inject
        def handler(
            db: Annotated[Database, container.Needs(Database)],
            logger: Annotated[Logger, container.Needs(Logger)],
            name: str,
        ) -> str:
            logger.info(f'Creating {name}')
            db.query(f'INSERT {name}')
            return name

        result = handler(name='John')

        assert result == 'John'
        assert logger.messages == ['Creating John']

    def test_skips_non_registered_params(self) -> None:
        container = Container()
        container.register(Database, FakeDB())

        @inject
        def handler(
            db: Annotated[Database, container.Needs(Database)],
            name: str,
            count: int = 0,
        ) -> tuple[str, int]:
            return name, count

        result = handler(name='test', count=5)

        assert result == ('test', 5)

    def test_explicit_kwarg_overrides_injection(self) -> None:
        container = Container()
        container.register(Database, FakeDB())

        custom_db = FakeDB()

        @inject
        def handler(db: Annotated[Database, container.Needs(Database)]) -> object:
            return db

        result = handler(db=custom_db)

        assert result is custom_db

    def test_supports_needs_callable_alongside_container(self) -> None:
        container = Container()
        container.register(Database, FakeDB())

        def get_config() -> dict[str, bool]:
            return {'debug': True}

        @inject
        def handler(
            db: Annotated[Database, container.Needs(Database)],
            config: Annotated[dict[str, bool], Needs(get_config)],
        ) -> tuple[object, dict[str, bool]]:
            return db, config

        db_result, config_result = handler()

        assert isinstance(db_result, FakeDB)
        assert config_result == {'debug': True}


class TestContainerInjectInit:
    def test_injects_into_init(self) -> None:
        container = Container()
        db = FakeDB()
        container.register(Database, db)

        class UserService:
            @inject
            def __init__(self, db: Annotated[Database, container.Needs(Database)]):
                self.db = db

        service = UserService()

        assert service.db is db

    def test_injects_multiple_deps_into_init(self) -> None:
        container = Container()
        db = FakeDB()
        logger = FakeLogger()
        container.register(Database, db)
        container.register(Logger, logger)

        class UserService:
            @inject
            def __init__(
                self,
                db: Annotated[Database, container.Needs(Database)],
                logger: Annotated[Logger, container.Needs(Logger)],
            ):
                self.db = db
                self.logger = logger

        service = UserService()

        assert service.db is db
        assert service.logger is logger

    def test_init_with_explicit_kwarg_override(self) -> None:
        container = Container()
        container.register(Database, FakeDB())

        custom_db = FakeDB()

        class UserService:
            @inject
            def __init__(self, db: Annotated[Database, container.Needs(Database)]):
                self.db = db

        service = UserService(db=custom_db)

        assert service.db is custom_db

    def test_init_with_regular_params_alongside_injection(self) -> None:
        container = Container()
        db = FakeDB()
        container.register(Database, db)

        class UserService:
            @inject
            def __init__(
                self,
                db: Annotated[Database, container.Needs(Database)],
                name: str,
            ):
                self.db = db
                self.name = name

        service = UserService(name='test')

        assert service.db is db
        assert service.name == 'test'


class TestContainerInjectAsync:
    @pytest.mark.asyncio
    async def test_injects_registered_type(self) -> None:
        container = Container()
        container.register(Database, FakeDB())

        @inject
        async def handler(
            db: Annotated[Database, container.Needs(Database)],
        ) -> list[dict[str, str]]:
            return db.query('SELECT 1')

        assert await handler() == [{'sql': 'SELECT 1'}]

    @pytest.mark.asyncio
    async def test_injects_multiple_types(self) -> None:
        container = Container()
        db = FakeDB()
        logger = FakeLogger()
        container.register(Database, db)
        container.register(Logger, logger)

        @inject
        async def handler(
            db: Annotated[Database, container.Needs(Database)],
            logger: Annotated[Logger, container.Needs(Logger)],
            name: str,
        ) -> str:
            logger.info(f'Creating {name}')
            return name

        result = await handler(name='Jane')

        assert result == 'Jane'
        assert logger.messages == ['Creating Jane']

    @pytest.mark.asyncio
    async def test_explicit_kwarg_overrides_injection(self) -> None:
        container = Container()
        container.register(Database, FakeDB())
        custom_db = FakeDB()

        @inject
        async def handler(
            db: Annotated[Database, container.Needs(Database)],
        ) -> object:
            return db

        result = await handler(db=custom_db)

        assert result is custom_db


class TestContainerThreadSafety:
    def test_concurrent_resolve_singleton(self) -> None:
        container = Container()
        db = FakeDB()
        container.register(Database, db)

        results: list[object] = []
        errors: list[Exception] = []

        def resolve_db() -> None:
            try:
                results.append(container.resolve(Database))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=resolve_db) for _ in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert len(results) == 50
        assert all(r is db for r in results)

    def test_concurrent_resolve_factory(self) -> None:
        container = Container()
        container.register(Database, FakeDB)

        with ThreadPoolExecutor(max_workers=10) as pool:
            futures = [pool.submit(container.resolve, Database) for _ in range(100)]
            results = [f.result() for f in as_completed(futures)]

        assert len(results) == 100
        assert all(isinstance(r, FakeDB) for r in results)
        assert len(set(id(r) for r in results)) > 1

    def test_concurrent_register_and_resolve(self) -> None:
        container = Container()
        container.register(Database, FakeDB())
        barrier = threading.Barrier(20)
        errors: list[Exception] = []

        def register_worker() -> None:
            barrier.wait()
            try:
                container.register(Database, FakeDB())
            except Exception as e:
                errors.append(e)

        def resolve_worker() -> None:
            barrier.wait()
            try:
                container.resolve(Database)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=register_worker if i % 2 == 0 else resolve_worker)
            for i in range(20)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors

    def test_concurrent_override(self) -> None:
        container = Container()
        original_db = FakeDB()
        container.register(Database, original_db)
        errors: list[Exception] = []

        def override_worker(i: int) -> None:
            try:
                with container.override(Database, FakeDB()):
                    result = container.resolve(Database)
                    assert isinstance(result, FakeDB)
            except Exception as e:
                errors.append(e)

        with ThreadPoolExecutor(max_workers=10) as pool:
            futures = [pool.submit(override_worker, i) for i in range(50)]
            for f in as_completed(futures):
                f.result()

        assert not errors
        assert container.resolve(Database) is original_db
