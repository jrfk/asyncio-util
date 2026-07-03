# Getting Started

## Requirements

- Python 3.10 or later (CPython or PyPy)
- No third-party dependencies

## Installation

!!! warning
    Not yet published to PyPI. Install from GitHub:

```console
pip install git+https://github.com/jrfk/asyncio-util
```

or with [uv](https://docs.astral.sh/uv/):

```console
uv add git+https://github.com/jrfk/asyncio-util
```

## Your first AsyncValue

An [`AsyncValue`][asyncio_util.AsyncValue] wraps an initial value. Read and
write it through the `value` property like a normal attribute:

```python
from asyncio_util import AsyncValue

score = AsyncValue(0)
print(score.value)   # 0
score.value = 10
print(score.value)   # 10
```

The difference from a plain attribute: other tasks can **await** it.

```python
import asyncio
from asyncio_util import AsyncValue

score = AsyncValue(0)

async def announcer():
    value = await score.wait_value(lambda v: v >= 100)
    print(f"reached {value}!")

async def game():
    for points in (30, 40, 50):
        await asyncio.sleep(0.1)
        score.value += points   # property supports augmented assignment

async def main():
    await asyncio.gather(announcer(), game())

asyncio.run(main())
```

Output:

```text
reached 120!
```

There is no polling here: `announcer()` sleeps until the assignment
`score.value += points` makes the predicate true, and it receives the exact
value that satisfied it.

## Values vs. predicates

Every waiting API accepts either a **plain value** (compared with `==`) or a
**predicate function**:

```python
await score.wait_value(100)               # value == 100
await score.wait_value(lambda v: v >= 100)  # predicate(value) is True
```

!!! tip "Waiting for `None`"
    A plain `None` is treated as a value like any other:
    `await av.wait_value(None)` waits until the value is `None`.

## Timeouts

`wait_value()` and `wait_transition()` accept a `timeout` argument and raise
`asyncio.TimeoutError` when it expires:

```python
try:
    await score.wait_value(100, timeout=1.0)
except asyncio.TimeoutError:
    print("timeout!")
```

The standard library idioms compose just as well — use whichever your
codebase prefers:

```python
await asyncio.wait_for(score.wait_value(100), timeout=1.0)   # 3.10+

async with asyncio.timeout(1.0):                             # 3.11+
    await score.wait_value(100)
```

When a wait is cancelled — by a timeout or otherwise — its internal waiter is
cleaned up immediately; nothing leaks.

## A note on equality

Assigning a value that compares equal (`==`) to the current one is a **no-op**:
no waiter wakes up and no transition is recorded. This deduplication is what
makes derived values (see [Deriving and composing](guide/deriving.md)) cheap.

## Thread safety

`AsyncValue` is **not thread-safe**. Assign `value` only from the thread
running the event loop. From another thread, hop onto the loop first:

```python
loop.call_soon_threadsafe(setattr, av, "value", 42)
```

## Next steps

- [Waiting for values](guide/waiting.md) — the full story on `wait_value`,
  `wait_transition` and `held_for`.
- [Iterating over changes](guide/iterating.md) — consuming values as streams.
- [Deriving and composing](guide/deriving.md) — building values out of values.
- [Tasks and cancellation](guide/tasks.md) — structured helpers beyond
  `AsyncValue`.
- [Events, streams and timing](guide/streams.md) — the rest of the toolbox.
