from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Dependant:
    """Node in the dependency tree representing a single injektable callable.

    Each node holds a reference to its callable and a list of sub-dependencies
    that must be resolved before the callable can be executed.

    Attributes:
        call: The callable that produces the dependency value.
        dependencies: Sub-dependencies required by this callable.
        param_name: The parameter name this dependency maps to in the parent.
    """

    call: Callable[..., Any]
    dependencies: list['Dependant'] = field(default_factory=list)
    param_name: str = ''
