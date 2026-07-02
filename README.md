# asyncio-util

[![Test](https://github.com/jrfk/asyncio-util/actions/workflows/test.yml/badge.svg)](https://github.com/jrfk/asyncio-util/actions/workflows/test.yml)
[![Docs](https://github.com/jrfk/asyncio-util/actions/workflows/docs.yml/badge.svg)](https://jrfk.github.io/asyncio-util/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://spdx.org/licenses/MIT.html)

**Utilities for asyncio, ported from [trio-util](https://github.com/groove-x/trio-util) —
awaitable values, cancel scopes, repeated events, and more.**

[Documentation](https://jrfk.github.io/asyncio-util/) | [日本語 README](README.ja.md) | [日本語ドキュメント](https://jrfk.github.io/asyncio-util/ja/)

> [!TIP]
> This project started as the sample code for a PyCon US 2024
> [talk](https://us.pycon.org/2024/schedule/presentation/142/) on porting
> trio-util to asyncio, and grew into a standalone library.

-----

The centerpiece is `AsyncValue`: a value whose states and transitions any
number of tasks can *await* — no polling loops, no hand-rolled `Event`
juggling, no missed wakeups:

```python
import asyncio
from asyncio_util import AsyncValue

connection_state = AsyncValue("disconnected")

async def watcher():
    # Wait until the value satisfies a condition...
    await connection_state.wait_value("connected")
    print("connected!")

    # ...or react to every change as it happens.
    async for state in connection_state.eventual_values():
        print(f"state is now: {state}")

async def main():
    task = asyncio.ensure_future(watcher())
    await asyncio.sleep(0)
    connection_state.value = "connecting"
    connection_state.value = "connected"
    await asyncio.sleep(0.1)
    task.cancel()

asyncio.run(main())
```

Matches are evaluated **synchronously at assignment time**, so a matching
change is never missed even if the value flips back immediately:

```python
av = AsyncValue(10)

# elsewhere: av.value = 20; av.value = 10   (rapid flip)
value = await av.wait_value(20)   # still returns 20
```

## Features

**Awaitable values**

- `AsyncValue` / `AsyncBool` — `wait_value()`, `wait_transition()`,
  `eventual_values()`, `transitions()`, with predicates, `timeout=`, and
  `held_for=` debouncing
- `open_transform(f)` — derive an `AsyncValue` tracking `f(value)`
- `compose_values(x=..., y=...)` — await conditions spanning several values
- `open_held_for()` / `open_hysteresis()` — time-based filters for flappy
  signals

**Tasks and cancellation**

- `wait_any()` / `wait_all()` / `wait_any_map()` — structured racing and
  joining (all started tasks are cancelled and awaited before returning)
- `move_on_when(trigger)` — cancel a block when an event fires
- `run_and_cancelling(fn)` / `start_and_cancelling(fn)` — background tasks
  scoped to a block

**Events, streams and timing**

- `RepeatedEvent` — an event that fires many times, with multiple listeners
- `MulticastQueue` — broadcast each item to every active listener
- `periodic(period)` — drift-free periodic iteration
- `azip()` / `azip_longest()` — async `zip` over async iterators
- `iter_move_on_after()` / `iter_fail_after()` — per-item timeouts

Zero dependencies, typed (`py.typed`), Python 3.10+ (CPython & PyPy).

## Installation

> [!WARNING]
> This project is not yet available on PyPI.

```console
pip install git+https://github.com/jrfk/asyncio-util
```

## Documentation

Full guides (English / 日本語) and API reference:
**https://jrfk.github.io/asyncio-util/**

Runnable examples live in [`examples/`](examples/).

## Development

```console
uv sync --group dev
uv run pytest              # tests
uv run mkdocs serve        # docs preview (uv sync --group docs)
```

## Acknowledgements

The API is modeled on [trio-util](https://github.com/groove-x/trio-util) by
GROOVE X, reimplemented from scratch on top of asyncio primitives.

## License

`asyncio-util` is distributed under the terms of the
[MIT](https://spdx.org/licenses/MIT.html) license.
