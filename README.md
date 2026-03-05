<h1 align="center">Injekta</h1>
<p align="center"><i>Lightweight, type-safe dependency injection for Python. One decorator, zero dependencies, full type inference</i></p>

<p align="center">
    <a href="https://codecov.io/gh/autoscrape-labs/injekta"><img src="https://codecov.io/gh/autoscrape-labs/injekta/graph/badge.svg" alt="Codecov"></a>
    <img src="https://github.com/autoscrape-labs/injekta/actions/workflows/ci.yml/badge.svg" alt="Tests">
    <img src="https://github.com/autoscrape-labs/injekta/actions/workflows/lint.yml/badge.svg" alt="Ruff">
    <img src="https://github.com/autoscrape-labs/injekta/actions/workflows/typecheck.yml/badge.svg" alt="MyPy">
    <img src="https://img.shields.io/badge/python-%3E%3D3.10-blue" alt="Python >= 3.10">
</p>


<p align="center">
    <a href="#quick-start">Getting Started</a> · <a href="#four-ways-to-declare-dependencies">Features</a> · <a href="#scoping-and-lifecycle">Lifecycle</a> · <a href="#error-handling">Errors</a> · <a href="#testing">Testing</a> · <a href="#license">License</a>
</p>

## Install

```bash
pip install injekta
```

## Quick start

```python
from typing import Annotated
from injekta import Needs, inject

def get_db() -> Database:
    return PostgresDB(os.environ["DATABASE_URL"])

@inject
def create_user(db: Annotated[Database, Needs(get_db)], name: str):
    db.execute(f"INSERT INTO users (name) VALUES ('{name}')")
    return {"created": name}

create_user(name="John")  # db is resolved automatically
```

That's it. No configuration, no boilerplate, no framework required.

## Why injekta?

If you've used FastAPI's `Depends`, injekta is that same idea extracted into a standalone library. Most DI libraries in Python are either too complex for what they do, or too magical to reason about. injekta takes a different approach:

- A single decorator (`@inject`) handles everything
- Dependencies are declared in the function signature, not in external config
- Full type inference, your editor knows the types, mypy validates them
- Zero runtime dependencies, just the standard library
- Works with both sync and async functions

## Four ways to declare dependencies

injekta supports four styles. Pick the one that fits your use case, or mix them freely.

### Factory (default value)

The simplest form. Pass a callable to `Needs` and use it as a default value.

```python
@inject
def handler(db: Database = Needs(get_db)):
    ...
```

Injected parameters must come after regular parameters in this style.

### Factory (Annotated)

Using `Annotated` places the dependency in the type hint, so parameter order is unrestricted.

```python
from typing import Annotated

@inject
def handler(db: Annotated[Database, Needs(get_db)], name: str):
    ...
```

### Container (default value)

For larger applications, register implementations in a `Container` and reference them by type.

```python
from injekta import Container

container = Container()
container.register(Database, PostgresDB())
container.register(Logger, ConsoleLogger())

@inject
def handler(db: Database = container.Needs(Database)):
    ...
```

Instances are singletons. Pass a class, lambda, or function to get a new value on each resolution:

```python
container.register(Database, PostgresDB)                          # class factory
container.register(Database, lambda: PostgresDB("localhost"))     # lambda factory
```

### Container (Annotated)

The recommended style for production code. Combines type safety with free parameter ordering.

```python
@inject
def handler(
    db: Annotated[Database, container.Needs(Database)],
    logger: Annotated[Logger, container.Needs(Logger)],
    name: str,
):
    logger.info(f"Creating {name}")
    db.execute("INSERT INTO users ...")
```

## Protocols over inheritance

injekta works naturally with Python's `Protocol` for structural typing. No base classes required.

```python
from typing import Protocol

class Database(Protocol):
    def execute(self, query: str) -> None: ...
    def fetch(self, query: str) -> list[dict]: ...

class Logger(Protocol):
    def info(self, msg: str) -> None: ...

# Concrete implementations don't inherit from the protocol
class PostgresDB:
    def execute(self, query: str) -> None: ...
    def fetch(self, query: str) -> list[dict]: ...

container = Container()
container.register(Database, PostgresDB())
```

## Class injection

`@inject` works on `__init__` methods, making it straightforward to build service classes.

```python
class UserService:
    @inject
    def __init__(
        self,
        db: Annotated[Database, container.Needs(Database)],
        logger: Annotated[Logger, container.Needs(Logger)],
    ):
        self.db = db
        self.logger = logger

    def create(self, name: str) -> None:
        self.logger.info(f"Creating {name}")
        self.db.execute(f"INSERT INTO users (name) VALUES ('{name}')")

service = UserService()  # dependencies injected automatically
```

## Async support

Both sync and async dependencies work transparently.

```python
async def get_db() -> Database:
    db = PostgresDB()
    await db.connect()
    return db

@inject
async def handler(db: Annotated[Database, Needs(get_db)]):
    await db.fetch("SELECT * FROM users")
```

## Yield dependencies

Dependencies that need cleanup (database connections, HTTP sessions, file handles) can use `yield` instead of `return`. Code after `yield` runs automatically when the function returns:

```python
def get_db() -> Generator[Database]:
    db = PostgresDB(os.environ["DATABASE_URL"])
    db.connect()
    yield db
    db.close()  # runs after handler returns

@inject
def handler(db: Database = Needs(get_db)):
    db.execute("INSERT INTO users ...")
```

Async generators work the same way:

```python
async def get_session() -> AsyncGenerator[ClientSession]:
    session = ClientSession()
    yield session
    await session.close()

@inject
async def handler(session: Annotated[ClientSession, Needs(get_session)]):
    await session.get("https://api.example.com")
```

Cleanup runs even if the function raises an exception.

## Nested dependencies

Dependencies can depend on other dependencies. injekta resolves the full tree.

```python
def get_config() -> Config:
    return Config.from_env()

def get_db(config: Config = Needs(get_config)) -> Database:
    return PostgresDB(config.database_url)

def get_user_repo(db: Database = Needs(get_db)) -> UserRepository:
    return UserRepository(db)

@inject
def handler(repo: UserRepository = Needs(get_user_repo)):
    return repo.list_all()

# Resolves: get_config -> get_db -> get_user_repo -> handler
```

## Scoping and lifecycle

Understanding how injekta manages instance lifetime avoids surprises.

### Signature analysis is cached

`@inject` analyzes the function signature **once at decoration time** and caches the dependency tree. Subsequent calls skip all introspection and go straight to resolution. This means there is zero reflection overhead per call.

### Factory functions (`Needs`)

Every call to the injected function re-executes the factory from scratch. There is no implicit caching between calls:

```python
def get_db() -> Database:
    print("connecting...")
    return PostgresDB()

@inject
def handler(db: Database = Needs(get_db)):
    ...

handler()  # prints "connecting..."
handler()  # prints "connecting..." again
```

Within a single call, if the same factory appears in multiple branches of the dependency tree (diamond dependency), it is executed only once:

```python
def get_config() -> Config:
    return Config.from_env()  # called once, not twice

def get_db(config: Config = Needs(get_config)) -> Database: ...
def get_cache(config: Config = Needs(get_config)) -> Cache: ...

@inject
def handler(
    db: Database = Needs(get_db),
    cache: Cache = Needs(get_cache),
):
    ...

handler()  # get_config runs once, result shared by get_db and get_cache
```

### Container: singletons vs factories

`Container.register` auto-detects the strategy based on what you pass:

| You register | Behavior | Example |
|---|---|---|
| An **instance** | Singleton. Same object returned every time. | `container.register(Database, PostgresDB())` |
| A **class** | Factory. New instance created on each resolution. | `container.register(Database, PostgresDB)` |
| A **function/lambda** | Factory. Called on each resolution. | `container.register(Database, lambda: PostgresDB("url"))` |

```python
container = Container()

# Singleton: same connection reused everywhere
db = PostgresDB(os.environ["DATABASE_URL"])
container.register(Database, db)

# Factory (class): fresh instance per resolution, no constructor args
container.register(Logger, ConsoleLogger)

# Factory (lambda): fresh instance with custom arguments
container.register(Database, lambda: PostgresDB("localhost", 5432))

# Factory (function): same as lambda, useful for complex setup
def make_cache() -> RedisCache:
    cache = RedisCache(os.environ["REDIS_URL"])
    cache.ping()
    return cache

container.register(Cache, make_cache)
```

Factories can also be decorated with `@inject` to receive their own dependencies:

```python
@inject
def make_service(db: Annotated[Database, container.Needs(Database)]) -> UserService:
    return UserService(db)

container.register(UserService, make_service)
```

If you need a singleton, instantiate it yourself and register the instance. If you need a fresh object every time, register a class, lambda, or function.

## Mixing styles

All four styles work together in the same function signature.

```python
@inject
def handler(
    db: Annotated[Database, container.Needs(Database)],  # container, Annotated
    config: Annotated[Config, Needs(get_config)],         # factory, Annotated
    cache: Cache = container.Needs(Cache),                 # container, default
    metrics: Metrics = Needs(get_metrics),                 # factory, default
    name: str = "",                                        # regular parameter
):
    ...
```

## Error handling

injekta raises clear, specific exceptions when something goes wrong:

| Exception | When | Phase |
|---|---|---|
| `ResolutionError` | Circular dependency, invalid signature | Decoration time (`@inject`) |
| `InjectionError` | Unregistered type, async dep in sync context | Call time (function execution) |
| `InjektaError` | Base class for all injekta errors | Catch-all |

```python
from injekta.exceptions import InjectionError, ResolutionError
```

**Unregistered type:**

```python
container.resolve(Database)
# InjectionError: No registration found for 'Database'
```

**Circular dependency:**

```python
def get_a(b=Needs(get_b)): ...
def get_b(a=Needs(get_a)): ...

@inject
def handler(a=Needs(get_a)): ...
# ResolutionError: Circular dependency detected for 'get_a'
```

**Async dependency in sync context:**

```python
async def get_db(): ...

@inject
def handler(db=Needs(get_db)): ...

handler()
# InjectionError: Cannot use async dependency 'get_db' in sync context.
```

All exceptions inherit from `InjektaError`, so you can catch them all with a single `except InjektaError`.

## Testing

Use `container.override` to swap dependencies in tests. The original registration is restored automatically when the context exits:

```python
def test_create_user():
    fake_db = FakeDB()

    with container.override(Database, fake_db):
        result = handler(name="John")

    assert result == "John"
    assert fake_db.last_query == "INSERT John"
```

Overrides are safe against exceptions and support nesting:

```python
def test_with_nested_overrides():
    with container.override(Database, FakeDB()):
        with container.override(Logger, FakeLogger()):
            result = handler(name="John")
```

Or bypass injection entirely by passing dependencies directly:

```python
def test_handler_directly():
    result = handler(db=FakeDB(), name="John")
```

## Thread safety

The `Container` is fully thread-safe. All operations (`register`, `resolve`, `override`) are protected by an internal lock, so it's safe to use a single container across multiple threads in any server model (Gunicorn, Uvicorn, threaded servers).

## License

MIT. See [LICENSE](LICENSE) for details.
