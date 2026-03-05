## 0.1.0 (2026-03-05)

### Feat

- **container**: add thread safety with RLock
- **project**: support Python 3.10+ with future annotations
- **solver**: add yield dependency support with automatic cleanup
- **container**: add override context manager for testing
- **container**: support functions and lambdas as factories in register
- **solver**: add per-cycle memoization for diamond dependency deduplication
- **resolver**: add Annotated type hint support for Needs markers
- **container**: add Container with type-based dependency injection
- **needs**: add generic type parameter for return type inference
- **core**: add @inject decorator and public API exports
- **core**: add dependency resolver and solver
- **core**: add exceptions, Needs marker, and Dependant model

### Fix

- **lint**: use anext() builtin and add test-specific ruff ignores

### Refactor

- **project**: rename package from injecta to injekta
- **container**: use guard clause in register method
- **core**: remove use_cache from Needs, Dependant, and solver
- **container**: replace container.inject with container.Needs
- **decorator**: extract shared wiring logic to _wiring module
- **tests**: update imports for new subpackage structure
- **core**: reorganize into subpackages
