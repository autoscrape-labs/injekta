from collections.abc import Callable
from typing import Any, Generic, TypeVar

T = TypeVar('T')


class Needs(Generic[T]):
    """Marker that declares a function parameter as a dependency to be injected.

    The return type of the dependency callable is preserved through the generic
    parameter `T`, enabling full type inference without explicit annotations.

    Args:
        dependency: The callable that provides the dependency value.
        use_cache: Whether to cache the result within a single resolution cycle.

    Example:
        ```python
        def get_db() -> Database:
            return Database()

        @inject
        def handler(db=Needs(get_db)):  # db is inferred as Database
            ...
        ```
    """

    __slots__ = ('dependency', 'use_cache')

    def __init__(self, dependency: Callable[..., T], *, use_cache: bool = True) -> None:
        self.dependency = dependency
        self.use_cache = use_cache

    def __repr__(self) -> str:
        name = getattr(self.dependency, '__name__', repr(self.dependency))
        return f'Needs({name}, use_cache={self.use_cache})'
