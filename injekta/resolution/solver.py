from __future__ import annotations

import inspect
from collections.abc import Callable
from contextlib import AsyncExitStack, ExitStack
from typing import Any

from injekta.core.models import Dependant
from injekta.exceptions import InjectionError


async def solve_dependencies(
    dependant: Dependant,
    _cache: dict[Callable[..., Any], Any] | None = None,
    _exit_stack: AsyncExitStack | None = None,
) -> dict[str, Any]:
    """Resolve a dependency tree asynchronously, executing each dependency.

    Traverses the tree depth-first, resolving sub-dependencies before their
    parents. Supports sync/async callables and sync/async generators (yield
    dependencies). Identical callables appearing in multiple branches are
    executed only once per resolution cycle (diamond dependency deduplication).

    Generator dependencies have their cleanup (code after ``yield``) executed
    when the resolution cycle ends.

    Args:
        dependant: The root of the dependency tree to resolve.

    Returns:
        A mapping of parameter names to their resolved values.
    """
    if _cache is None:
        _cache = {}
    if _exit_stack is None:
        _exit_stack = AsyncExitStack()

    values: dict[str, Any] = {}

    for sub_dep in dependant.dependencies:
        if sub_dep.call in _cache:
            values[sub_dep.param_name] = _cache[sub_dep.call]
            continue

        sub_values = await solve_dependencies(sub_dep, _cache, _exit_stack)
        result = await _execute(sub_dep.call, sub_values, _exit_stack)
        _cache[sub_dep.call] = result
        values[sub_dep.param_name] = result

    return values


def solve_dependencies_sync(
    dependant: Dependant,
    _cache: dict[Callable[..., Any], Any] | None = None,
    _exit_stack: ExitStack | None = None,
) -> dict[str, Any]:
    """Resolve a dependency tree synchronously.

    Same as `solve_dependencies` but only supports sync callables and
    sync generators. Raises `InjectionError` if an async dependency is
    encountered.

    Args:
        dependant: The root of the dependency tree to resolve.

    Returns:
        A mapping of parameter names to their resolved values.

    Raises:
        InjectionError: If an async callable is found in the tree.
    """
    if _cache is None:
        _cache = {}
    if _exit_stack is None:
        _exit_stack = ExitStack()

    values: dict[str, Any] = {}

    for sub_dep in dependant.dependencies:
        if inspect.iscoroutinefunction(sub_dep.call) or inspect.isasyncgenfunction(sub_dep.call):
            raise InjectionError(
                f"Cannot use async dependency '{sub_dep.call.__name__}' in sync context. "
                f'Use an async function with @inject instead.'
            )

        if sub_dep.call in _cache:
            values[sub_dep.param_name] = _cache[sub_dep.call]
            continue

        sub_values = solve_dependencies_sync(sub_dep, _cache, _exit_stack)
        result = _execute_sync(sub_dep.call, sub_values, _exit_stack)
        _cache[sub_dep.call] = result
        values[sub_dep.param_name] = result

    return values


async def _execute(
    call: Callable[..., Any],
    kwargs: dict[str, Any],
    exit_stack: AsyncExitStack,
) -> Any:
    if inspect.isasyncgenfunction(call):
        return await exit_stack.enter_async_context(_async_gen_to_cm(call, kwargs))
    if inspect.isgeneratorfunction(call):
        return exit_stack.enter_context(_gen_to_cm(call, kwargs))
    if inspect.iscoroutinefunction(call):
        return await call(**kwargs)
    return call(**kwargs)


def _execute_sync(
    call: Callable[..., Any],
    kwargs: dict[str, Any],
    exit_stack: ExitStack,
) -> Any:
    if inspect.isgeneratorfunction(call):
        return exit_stack.enter_context(_gen_to_cm(call, kwargs))
    return call(**kwargs)


from contextlib import asynccontextmanager, contextmanager  # noqa: E402


@contextmanager
def _gen_to_cm(call: Callable[..., Any], kwargs: dict[str, Any]) -> Any:
    gen = call(**kwargs)
    try:
        yield next(gen)
    finally:
        try:
            next(gen)
        except StopIteration:
            pass


@asynccontextmanager
async def _async_gen_to_cm(call: Callable[..., Any], kwargs: dict[str, Any]) -> Any:
    agen = call(**kwargs)
    try:
        yield await anext(agen)
    finally:
        try:
            await anext(agen)
        except StopAsyncIteration:
            pass
