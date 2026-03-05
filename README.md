# Injecta: lightweight, type-safe dependency injection for Python

One decorator, zero dependencies, full type inference. Python 3.12+.

## Table of contents

- [Install](#install)
- [Quick start](#quick-start)
- [Why injecta?](#why-injecta)
- [Four ways to declare dependencies](#four-ways-to-declare-dependencies)
- [Protocols over inheritance](#protocols-over-inheritance)
- [Class injection](#class-injection)
- [Async support](#async-support)
- [Nested dependencies](#nested-dependencies)
- [Mixing styles](#mixing-styles)
- [Testing](#testing)
- [License](#license)

## Install

```bash
pip install injecta
```

## Quick start

```python
from typing import Annotated
from injecta import Needs, inject

def get_db() -> Database:
    return PostgresDB(os.environ["DATABASE_URL"])

@inject
def create_user(db: Annotated[Database, Needs(get_db)], name: str):
    db.execute(f"INSERT INTO users (name) VALUES ('{name}')")
    return {"created": name}

create_user(name="John")  # db is resolved automatically
```

That's it. No configuration, no boilerplate, no framework required.

## Why injecta?

If you've used FastAPI's `Depends`, injecta is that same idea extracted into a standalone library. Most DI libraries in Python are either too complex for what they do, or too magical to reason about. injecta takes a different approach:

- A single decorator (`@inject`) handles everything
- Dependencies are declared in the function signature, not in external config
- Full type inference, your editor knows the types, mypy validates them
- Zero runtime dependencies, just the standard library
- Works with both sync and async functions

## Four ways to declare dependencies

injecta supports four styles. Pick the one that fits your use case, or mix them freely.

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
from injecta import Container

container = Container()
container.register(Database, PostgresDB())
container.register(Logger, ConsoleLogger())

@inject
def handler(db: Database = container.Needs(Database)):
    ...
```

Instances are singletons. Pass a class instead to get a new instance on each resolution:

```python
container.register(Database, PostgresDB)  # factory, new instance every time
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

injecta works naturally with Python's `Protocol` for structural typing. No base classes required.

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

## Nested dependencies

Dependencies can depend on other dependencies. injecta resolves the full tree.

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

## Testing

Replace dependencies easily in tests. Use a fresh container per test to avoid shared state:

```python
def test_create_user():
    test_container = Container()
    fake_db = FakeDB()
    test_container.register(Database, fake_db)

    @inject
    def handler(db: Annotated[Database, test_container.Needs(Database)], name: str):
        db.execute(f"INSERT {name}")
        return name

    result = handler(name="John")

    assert result == "John"
    assert fake_db.last_query == "INSERT John"
```

Or bypass injection entirely by passing dependencies directly:

```python
def test_handler_directly():
    result = handler(db=FakeDB(), name="John")
```

## License

MIT. See [LICENSE](LICENSE) for details.
