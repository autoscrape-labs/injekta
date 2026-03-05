from collections.abc import Callable
from typing import Any


class Needs:
    """Marker that declares a function parameter as a dependency to be injected.

    Used as a default value in function signatures to indicate that the parameter
    should be resolved automatically by the `@inject` decorator.

    Args:
        dependency: The callable that provides the dependency value.
        use_cache: Whether to cache the result within a single resolution cycle.

    Example:
        ```python
        def get_db() -> Database:
            return Database()

        @inject
        def handler(db: Database = Needs(get_db)):
            ...
        ```
    """

    __slots__ = ('dependency', 'use_cache')

    def __init__(self, dependency: Callable[..., Any], *, use_cache: bool = True) -> None:
        self.dependency = dependency
        self.use_cache = use_cache

    def __repr__(self) -> str:
        name = getattr(self.dependency, '__name__', repr(self.dependency))
        return f'Needs({name}, use_cache={self.use_cache})'
