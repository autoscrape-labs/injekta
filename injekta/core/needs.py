from __future__ import annotations

from collections.abc import Callable
from typing import Generic, TypeVar

T = TypeVar('T')


class Needs(Generic[T]):
    """Marker that declares a function parameter as a dependency to be injected.

    The return type of the dependency callable is preserved through the generic
    parameter `T`, enabling full type inference without explicit annotations.

    Args:
        dependency: The callable that provides the dependency value.

    Example:
        ```python
        def get_db() -> Database:
            return Database()

        @inject
        def handler(db=Needs(get_db)):  # db is inferred as Database
            ...
        ```
    """

    __slots__ = ('dependency',)

    def __init__(self, dependency: Callable[..., T]) -> None:
        self.dependency = dependency

    def __repr__(self) -> str:
        name = getattr(self.dependency, '__name__', repr(self.dependency))
        return f'Needs({name})'
