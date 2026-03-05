import inspect
from collections.abc import Callable
from typing import Any

from injecta.exceptions import InjectionError
from injecta.models import Dependant


async def solve_dependencies(
    dependant: Dependant,
    cache: dict[Callable[..., Any], Any] | None = None,
) -> dict[str, Any]:
    """Resolve a dependency tree asynchronously, executing each dependency.

    Traverses the tree depth-first, resolving sub-dependencies before their
    parents. Supports both sync and async callables. Results are cached per
    callable within the resolution cycle when `use_cache` is enabled.

    Args:
        dependant: The root of the dependency tree to resolve.
        cache: Shared cache for the current resolution cycle.

    Returns:
        A mapping of parameter names to their resolved values.
    """
    if cache is None:
        cache = {}

    values: dict[str, Any] = {}

    for sub_dep in dependant.dependencies:
        if sub_dep.use_cache and sub_dep.call in cache:
            values[sub_dep.param_name] = cache[sub_dep.call]
            continue

        sub_values = await solve_dependencies(sub_dep, cache)
        result = await _execute(sub_dep.call, sub_values)

        if sub_dep.use_cache:
            cache[sub_dep.call] = result

        values[sub_dep.param_name] = result

    return values


def solve_dependencies_sync(
    dependant: Dependant,
    cache: dict[Callable[..., Any], Any] | None = None,
) -> dict[str, Any]:
    """Resolve a dependency tree synchronously.

    Same as `solve_dependencies` but only supports sync callables.
    Raises `InjectionError` if an async dependency is encountered.

    Args:
        dependant: The root of the dependency tree to resolve.
        cache: Shared cache for the current resolution cycle.

    Returns:
        A mapping of parameter names to their resolved values.

    Raises:
        InjectionError: If an async callable is found in the tree.
    """
    if cache is None:
        cache = {}

    values: dict[str, Any] = {}

    for sub_dep in dependant.dependencies:
        if inspect.iscoroutinefunction(sub_dep.call):
            raise InjectionError(
                f"Cannot use async dependency '{sub_dep.call.__name__}' in sync context. "
                f"Use an async function with @inject instead."
            )

        if sub_dep.use_cache and sub_dep.call in cache:
            values[sub_dep.param_name] = cache[sub_dep.call]
            continue

        sub_values = solve_dependencies_sync(sub_dep, cache)
        result = sub_dep.call(**sub_values)

        if sub_dep.use_cache:
            cache[sub_dep.call] = result

        values[sub_dep.param_name] = result

    return values


async def _execute(call: Callable[..., Any], kwargs: dict[str, Any]) -> Any:
    if inspect.iscoroutinefunction(call):
        return await call(**kwargs)
    return call(**kwargs)
