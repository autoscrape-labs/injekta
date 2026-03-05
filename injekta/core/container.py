from __future__ import annotations

import inspect
import threading
from collections.abc import Callable, Generator
from contextlib import contextmanager
from typing import Any, TypeVar

from injekta.core.needs import Needs as NeedsMarker
from injekta.exceptions import InjectionError

T = TypeVar('T')


class Container:
    """Dependency injection container that resolves dependencies by type.

    Stores mappings from protocol/abstract types to their implementations.
    Instances are treated as singletons, classes/callables as factories
    that produce a new instance on each resolution. Async callables are
    stored as async factories and resolved via `resolve_async()` or
    automatically when used with `@inject` on an async function.

    Use `container.Needs(Type)` to create a `Needs` marker bound to this
    container, then combine with `@inject` as usual.

    Example:
        ```python
        container = Container()
        container.register(Database, PostgresDB())
        container.register(Logger, ConsoleLogger)

        @inject
        def handler(
            db=container.Needs(Database),
            logger=container.Needs(Logger),
            name: str,
        ):
            ...

        handler(name="John")  # db and logger resolved from container
        ```
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._singletons: dict[type[Any], Any] = {}
        self._factories: dict[type[Any], Callable[..., Any]] = {}
        self._async_factories: dict[type[Any], Callable[..., Any]] = {}

    def register(self, protocol: type[T], implementation: T | type[T] | Callable[..., T]) -> None:
        """Register a dependency for a given type.

        If `implementation` is an async callable, it's treated as an async
        factory. If it's a class or sync function, it's treated as a sync
        factory (new value per resolution). If it's an instance, it's
        treated as a singleton.

        Args:
            protocol: The type to register (typically a Protocol class).
            implementation: A concrete instance (singleton), class (factory),
                or callable (sync/async factory).
        """
        with self._lock:
            self._singletons.pop(protocol, None)
            self._factories.pop(protocol, None)
            self._async_factories.pop(protocol, None)

            if inspect.iscoroutinefunction(implementation):
                self._async_factories[protocol] = implementation
            elif isinstance(implementation, type) or inspect.isfunction(implementation):
                self._factories[protocol] = implementation
            else:
                self._singletons[protocol] = implementation

    def resolve(self, protocol: type[T]) -> T:
        """Resolve a dependency synchronously by its registered type.

        Args:
            protocol: The type to look up.

        Returns:
            The registered instance or a new instance from the factory.

        Raises:
            InjectionError: If no registration exists for the type, or if
                the registered factory is async.
        """
        with self._lock:
            if protocol in self._singletons:
                return self._singletons[protocol]  # type: ignore[no-any-return]

            if protocol in self._factories:
                return self._factories[protocol]()  # type: ignore[no-any-return]

            if protocol in self._async_factories:
                raise InjectionError(
                    f"Cannot resolve async factory for '{protocol.__name__}' synchronously. "
                    f'Use resolve_async() or an async context with @inject.'
                )

            raise InjectionError(f"No registration found for '{protocol.__name__}'")

    async def resolve_async(self, protocol: type[T]) -> T:
        """Resolve a dependency asynchronously by its registered type.

        Supports all registration types: singletons, sync factories, and
        async factories. Prefer this over `resolve()` when working in
        async contexts with async factories.

        Args:
            protocol: The type to look up.

        Returns:
            The registered instance or a new instance from the factory.

        Raises:
            InjectionError: If no registration exists for the type.
        """
        with self._lock:
            if protocol in self._singletons:
                return self._singletons[protocol]  # type: ignore[no-any-return]

            if protocol in self._async_factories:
                factory = self._async_factories[protocol]
            elif protocol in self._factories:
                return self._factories[protocol]()  # type: ignore[no-any-return]
            else:
                raise InjectionError(f"No registration found for '{protocol.__name__}'")

        return await factory()  # type: ignore[no-any-return]

    def Needs(self, protocol: type[T]) -> NeedsMarker[T]:  # noqa: N802
        """Create a `Needs` marker bound to this container.

        Returns a `Needs` instance whose dependency resolves from this
        container by type. Works seamlessly with the `@inject` decorator.

        If the registered implementation is an async factory, the marker
        wraps an async resolver so that `@inject` can await it correctly.

        Args:
            protocol: The type to resolve from this container.

        Returns:
            A `Needs` marker that resolves `protocol` from this container.

        Example:
            ```python
            @inject
            def handler(db=container.Needs(Database)):
                db.query(...)
            ```
        """
        with self._lock:
            is_async = protocol in self._async_factories

        if is_async:

            async def _resolve_async() -> T:
                return await self.resolve_async(protocol)

            return NeedsMarker(_resolve_async)

        return NeedsMarker(lambda: self.resolve(protocol))

    @contextmanager
    def override(
        self,
        protocol: type[T],
        implementation: T | type[T] | Callable[..., T],
    ) -> Generator[None]:
        """Temporarily replace a registration for the duration of the context.

        Restores the original registration (or removes the override if there
        was none) when the context exits. Supports nesting.

        Warning:
            Designed for **testing only**. In a multi-threaded environment,
            overrides are visible to all threads sharing this container
            instance, which can cause unpredictable behavior if used
            concurrently in production code.

        Args:
            protocol: The type to override.
            implementation: The replacement instance, class, or callable.

        Example:
            ```python
            with container.override(Database, FakeDB()):
                handler()  # uses FakeDB
            # original registration restored
            ```
        """
        with self._lock:
            had_singleton = protocol in self._singletons
            had_factory = protocol in self._factories
            had_async_factory = protocol in self._async_factories
            prev_singleton = self._singletons.get(protocol)
            prev_factory = self._factories.get(protocol)
            prev_async_factory = self._async_factories.get(protocol)

            self._singletons.pop(protocol, None)
            self._factories.pop(protocol, None)
            self._async_factories.pop(protocol, None)
            self.register(protocol, implementation)

        try:
            yield
        finally:
            with self._lock:
                self._singletons.pop(protocol, None)
                self._factories.pop(protocol, None)
                self._async_factories.pop(protocol, None)

                if had_singleton:
                    self._singletons[protocol] = prev_singleton
                if had_factory and prev_factory is not None:
                    self._factories[protocol] = prev_factory
                if had_async_factory and prev_async_factory is not None:
                    self._async_factories[protocol] = prev_async_factory
