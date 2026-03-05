from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Annotated, Any, get_args, get_origin

from injekta.core.models import Dependant
from injekta.core.needs import Needs
from injekta.exceptions import ResolutionError


def resolve_dependencies(
    call: Callable[..., Any],
    _stack: frozenset[Callable[..., Any]] | None = None,
) -> Dependant:
    """Analyze a callable's signature and build its dependency tree.

    Inspects each parameter for `Needs()` markers in both default values
    and `Annotated` type hints, then recursively resolves sub-dependencies.

    Supports two styles:
        - `db: Database = Needs(get_db)` (default value)
        - `db: Annotated[Database, Needs(get_db)]` (annotation)

    Args:
        call: The callable to analyze.

    Returns:
        A `Dependant` tree representing the full dependency graph.

    Raises:
        ResolutionError: If a circular dependency is detected.
    """
    if _stack is None:
        _stack = frozenset()

    if call in _stack:
        raise ResolutionError(
            f"Circular dependency detected for '{getattr(call, '__name__', repr(call))}'"
        )

    current_stack = _stack | {call}
    dependant = Dependant(call=call)
    signature = inspect.signature(call)

    for param_name, param in signature.parameters.items():
        needs = _extract_needs(param)
        if needs is None:
            continue

        sub_dependant = resolve_dependencies(needs.dependency, current_stack)
        sub_dependant.param_name = param_name
        dependant.dependencies.append(sub_dependant)

    return dependant


def _extract_needs(param: inspect.Parameter) -> Needs[Any] | None:
    if isinstance(param.default, Needs):
        return param.default

    if get_origin(param.annotation) is not Annotated:
        return None

    for arg in get_args(param.annotation):
        if isinstance(arg, Needs):
            return arg

    return None
