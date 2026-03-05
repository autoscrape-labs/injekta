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
    that produce a new instance on each resolution.

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

    def register(self, protocol: type[T], implementation: T | type[T] | Callable[..., T]) -> None:
        """Register a dependency for a given type.

        If `implementation` is a class or function, it's treated as a factory
        (new value per resolution). If it's an instance, it's treated as a
        singleton.

        Args:
            protocol: The type to register (typically a Protocol class).
            implementation: A concrete instance (singleton), class (factory),
                or callable (factory).
        """
        with self._lock:
            if isinstance(implementation, type) or inspect.isfunction(implementation):
                self._factories[protocol] = implementation
                return
            self._singletons[protocol] = implementation

    def resolve(self, protocol: type[T]) -> T:
        """Resolve a dependency by its registered type.

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

            if protocol in self._factories:
                return self._factories[protocol]()  # type: ignore[no-any-return]

            raise InjectionError(f"No registration found for '{protocol.__name__}'")

    def Needs(self, protocol: type[T]) -> NeedsMarker[T]:  # noqa: N802
        """Create a `Needs` marker bound to this container.

        Returns a `Needs` instance whose dependency resolves from this
        container by type. Works seamlessly with the `@inject` decorator.

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
            prev_singleton = self._singletons.get(protocol)
            prev_factory = self._factories.get(protocol)

            self._singletons.pop(protocol, None)
            self._factories.pop(protocol, None)
            self.register(protocol, implementation)

        try:
            yield
        finally:
            with self._lock:
                self._singletons.pop(protocol, None)
                self._factories.pop(protocol, None)

                if had_singleton:
                    self._singletons[protocol] = prev_singleton
                if had_factory and prev_factory is not None:
                    self._factories[protocol] = prev_factory
