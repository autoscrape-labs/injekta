class InjectaError(Exception):
    """Base exception for all injecta errors."""


class ResolutionError(InjectaError):
    """Raised when the dependency tree cannot be built.

    This typically indicates structural issues like circular dependencies
    or invalid function signatures.
    """


class InjectionError(InjectaError):
    """Raised when dependencies cannot be resolved at runtime.

    This covers issues like using async dependencies in a sync context.
    """
