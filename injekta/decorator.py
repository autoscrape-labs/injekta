from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from contextlib import AsyncExitStack, ExitStack
from functools import wraps
from typing import Any, ParamSpec, TypeVar, overload

from injekta.resolution.resolver import resolve_dependencies
from injekta.resolution.solver import solve_dependencies, solve_dependencies_sync

P = ParamSpec('P')
R = TypeVar('R')


@overload
def inject(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]: ...


@overload
def inject(func: Callable[P, R]) -> Callable[P, R]: ...


def inject(func: Callable[P, Any]) -> Callable[P, Any]:
    """Decorator that resolves and injects dependencies marked with `Needs()`.

    Analyzes the function signature once at decoration time, then resolves
    all dependencies on each call. Supports both sync and async functions.
    Generator dependencies (yield) are cleaned up after the function returns.

    Args:
        func: The function to decorate.

    Returns:
        A wrapper that auto-injects dependencies before calling the original function.

    Example:
        ```python
        @inject
        def handler(db=Needs(get_db), logger=container.Needs(Logger)):
            ...
        ```
    """
    dependant = resolve_dependencies(func)
    sig = inspect.signature(func)

    if inspect.iscoroutinefunction(func):

        @wraps(func)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
            async with AsyncExitStack() as exit_stack:
                dep_values = await solve_dependencies(dependant, _exit_stack=exit_stack)
                bound = sig.bind_partial(*args, **kwargs)
                for key, value in dep_values.items():
                    if key not in bound.arguments:
                        kwargs[key] = value
                return await func(*args, **kwargs)

        return async_wrapper

    @wraps(func)
    def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
        with ExitStack() as exit_stack:
            dep_values = solve_dependencies_sync(dependant, _exit_stack=exit_stack)
            bound = sig.bind_partial(*args, **kwargs)
            for key, value in dep_values.items():
                if key not in bound.arguments:
                    kwargs[key] = value
            return func(*args, **kwargs)

    return sync_wrapper
