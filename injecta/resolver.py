import inspect
from collections.abc import Callable
from typing import Any

from injecta.exceptions import ResolutionError
from injecta.models import Dependant
from injecta.needs import Needs


def resolve_dependencies(
    call: Callable[..., Any],
    _stack: frozenset[Callable[..., Any]] | None = None,
) -> Dependant:
    """Analyze a callable's signature and build its dependency tree.

    Inspects each parameter for `Needs()` markers and recursively resolves
    sub-dependencies, producing a complete `Dependant` tree.

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
        if not isinstance(param.default, Needs):
            continue

        sub_dependant = resolve_dependencies(param.default.dependency, current_stack)
        sub_dependant.param_name = param_name
        sub_dependant.use_cache = param.default.use_cache
        dependant.dependencies.append(sub_dependant)

    return dependant
