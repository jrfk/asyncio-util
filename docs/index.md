# asyncio-util

**Utilities for asyncio, ported from trio-util — awaitable values, cancel
scopes, repeated events, and more.**

`asyncio-util` brings the ergonomics of
[trio-util](https://github.com/groove-x/trio-util) (by GROOVE X) to plain
asyncio. Its centerpiece is [`AsyncValue`][asyncio_util.AsyncValue]: a value
whose states and transitions any number of tasks can *await* — no polling
loops, no hand-rolled `Event` juggling, no missed wakeups.

!!! info "Origin"
    This project started as the sample code for a
    [PyCon US 2024 talk](https://us.pycon.org/2024/schedule/presentation/142/)
    on porting trio-util to asyncio, and grew into a standalone library.

```python
import asyncio
from asyncio_util import AsyncValue

connection_state = AsyncValue("disconnected")

async def watcher():
    await connection_state.wait_value("connected")
    print("connected!")

async def main():
    task = asyncio.ensure_future(watcher())
    await asyncio.sleep(0)
    connection_state.value = "connected"   # wakes the watcher
    await task

asyncio.run(main())
```

## Why AsyncValue?

Shared state plus `asyncio.Event` is the usual way to signal between tasks —
and it is surprisingly easy to get wrong:

- An `Event` carries no value; you must keep the state next to it and keep
  the two in sync yourself.
- "Wait until X > 3" requires a loop of *check → wait → clear* that has to be
  written carefully to avoid lost wakeups.
- If the value changes twice before the waiting task runs, the intermediate
  value is silently lost. A task waiting for `20` misses the moment when the
  value was `20` and has already moved on.

`AsyncValue` solves all three: the value and its signaling live in one
object, waiting is one `await`, and matches are evaluated **synchronously at
assignment time** — so a matching change is never missed, even if the value
flips back immediately:

```python
av = AsyncValue(10)

# elsewhere: av.value = 20; av.value = 10   (rapid flip)
value = await av.wait_value(20)   # still returns 20
```

## Feature overview

### Awaitable values

| API | What it does |
| --- | --- |
| [`AsyncValue`][asyncio_util.AsyncValue] | A value whose states and transitions can be awaited |
| [`AsyncBool`][asyncio_util.AsyncBool] | `AsyncValue[bool]` with a `False` default |
| [`wait_value()`][asyncio_util.AsyncValue.wait_value] | Wait until the value matches a value or predicate |
| [`wait_transition()`][asyncio_util.AsyncValue.wait_transition] | Wait for the next matching *change* (edge) |
| [`eventual_values()`][asyncio_util.AsyncValue.eventual_values] | Iterate over values, always converging to the latest |
| [`transitions()`][asyncio_util.AsyncValue.transitions] | Iterate over `(new, old)` change pairs |
| [`open_transform()`][asyncio_util.AsyncValue.open_transform] | Derive an `AsyncValue` tracking `f(value)` |
| [`compose_values()`][asyncio_util.compose_values] | Combine several `AsyncValue`s and await cross-value conditions |
| [`open_held_for()`][asyncio_util.open_held_for] | An `AsyncBool` that turns True when a value has been stable |
| [`open_hysteresis()`][asyncio_util.open_hysteresis] | Hysteresis filtering for a boolean value |

### Tasks and cancellation

| API | What it does |
| --- | --- |
| [`wait_any()`][asyncio_util.wait_any] | Run coroutines concurrently, return on the first to finish |
| [`wait_all()`][asyncio_util.wait_all] | Run coroutines concurrently, return when all finish |
| [`wait_any_map()`][asyncio_util.wait_any_map] | `wait_any` that tells you *which* finished, with its result |
| [`move_on_when()`][asyncio_util.move_on_when] | Cancel a block when a trigger completes |
| [`run_and_cancelling()`][asyncio_util.run_and_cancelling] | Run a background task scoped to a block |
| [`start_and_cancelling()`][asyncio_util.start_and_cancelling] | Same, but waits for the task to signal readiness |

### Events, streams and timing

| API | What it does |
| --- | --- |
| [`RepeatedEvent`][asyncio_util.RepeatedEvent] | An event that can fire many times, with multiple listeners |
| [`MulticastQueue`][asyncio_util.MulticastQueue] | Broadcast each item to every active listener |
| [`periodic()`][asyncio_util.periodic] | Drift-free periodic iteration |
| [`azip()` / `azip_longest()`][asyncio_util.azip] | Async `zip` over async iterators |
| [`iter_move_on_after()` / `iter_fail_after()`][asyncio_util.iter_move_on_after] | Per-item timeouts for async iterators |

- **Zero dependencies** — only the standard library.
- **Typed** — ships a `py.typed` marker; `AsyncValue` is generic
  (`AsyncValue[int]`, `AsyncValue[State]`, …).
- **Python 3.10+**, CPython and PyPy.

## Installation

!!! warning
    Not yet published to PyPI. Install from GitHub:

```console
pip install git+https://github.com/jrfk/asyncio-util
```

## Where to go next

- [Getting Started](getting-started.md) — install and first steps.
- [Waiting for values](guide/waiting.md) — `wait_value`, `wait_transition`,
  timeouts and `held_for`.
- [Iterating over changes](guide/iterating.md) — `eventual_values` and
  `transitions`, and their exact semantics.
- [Deriving and composing](guide/deriving.md) — `open_transform`,
  `compose_values`, `open_held_for`, `open_hysteresis`.
- [Tasks and cancellation](guide/tasks.md) — `wait_any`, `move_on_when` and
  friends.
- [Events, streams and timing](guide/streams.md) — `RepeatedEvent`,
  `MulticastQueue`, `periodic`, async iteration helpers.
- [API Reference](api.md) — every public symbol, with source.

## Acknowledgements

The API is modeled on [trio-util](https://github.com/groove-x/trio-util) by
GROOVE X, reimplemented on top of asyncio primitives.
