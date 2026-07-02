# Events, streams and timing

Beyond awaitable values, `asyncio-util` ships a small toolbox for recurring
events, broadcasting, periodic work, and iterating multiple async sources.

## RepeatedEvent — an event that fires many times

`asyncio.Event` is one-shot: once set, every `wait()` returns immediately
until someone remembers to `clear()` it — a classic source of races.
[`RepeatedEvent`][asyncio_util.RepeatedEvent] models the "something happened
(again)" pattern directly:

```python
from asyncio_util import RepeatedEvent

changed = RepeatedEvent()

# Producer:
changed.set()          # fire; call as often as you like

# Consumer — wait for the next firing after this point:
await changed.wait()
```

Two iteration styles, mirroring [`eventual_values` vs `transitions`](iterating.md):

```python
# Never miss "there was at least one firing" (eventual consistency):
async for _ in changed.events():
    await rebuild_index()

# Only react while actually waiting; firings during the body are dropped:
async for _ in changed.unqueued_events():
    await redraw()
```

`events(repeat_last=True)` additionally yields once immediately — useful when
the consumer wants to process the current state on startup.

## MulticastQueue — broadcast to every listener

An `asyncio.Queue` delivers each item to *one* consumer.
[`MulticastQueue`][asyncio_util.MulticastQueue] delivers each item to
**every active listener**:

```python
from asyncio_util import MulticastQueue

mq: MulticastQueue[str] = MulticastQueue()

async def subscriber(name: str):
    async with mq.listen() as items:
        async for item in items:
            print(name, "got", item)

# elsewhere:
await mq.broadcast("hello")
```

- Listeners only receive items broadcast **while they are subscribed**
  (inside `listen()`).
- Iteration ends cleanly when the listener unsubscribes.

!!! warning "Lossy by design"
    Each listener has a bounded buffer (`queue_size`, default 10). If a
    listener falls behind and its buffer fills up, new items for *that
    listener* are silently dropped. Size the buffer for your slowest
    consumer, or drain faster.

## periodic — drift-free intervals

Sleeping `period` seconds in a loop drifts: each iteration adds the body's
runtime to the schedule. [`periodic()`][asyncio_util.periodic] targets fixed
points on the clock instead and tells you the actual timing:

```python
from asyncio_util import periodic

async for elapsed, delta in periodic(1.0):
    print(f"{elapsed:.1f}s since start, {delta}s since last")
    await poll_sensors()
```

- `elapsed` — seconds since the loop started; `delta` — seconds since the
  previous iteration (`None` on the first).
- If the body overruns the period, the next iteration starts immediately —
  overruns are not "queued up".

## azip / azip_longest — zip for async iterators

[`azip()`][asyncio_util.azip] advances several async iterators
**concurrently** (not one after the other) and yields result tuples:

```python
from asyncio_util import azip, azip_longest

async for left, right in azip(sensor_a.eventual_values(),
                              sensor_b.eventual_values()):
    compare(left, right)
```

`azip` stops at the shortest source;
[`azip_longest()`][asyncio_util.azip_longest] continues until all are
exhausted, substituting `fillvalue` (default `None`) for finished ones.

## iter_move_on_after / iter_fail_after — per-item timeouts

Bound how long you are willing to wait **between items** of any async
iterator:

```python
from asyncio_util import iter_move_on_after, iter_fail_after

# Stop iterating silently if no item arrives within 1s:
async for msg in iter_move_on_after(1.0, message_stream):
    handle(msg)

# Or make a stall an error:
async for msg in iter_fail_after(1.0, message_stream):   # asyncio.TimeoutError
    handle(msg)
```

The timeout applies to each `__anext__` call, not to the whole iteration.

## Choosing between them

| You want to… | Reach for |
| --- | --- |
| signal "it happened (again)" between tasks | `RepeatedEvent` |
| fan one stream out to many consumers | `MulticastQueue` |
| run something every N seconds without drift | `periodic` |
| consume several async sources in lockstep | `azip` / `azip_longest` |
| give up (or fail) on a stalled stream | `iter_move_on_after` / `iter_fail_after` |
| carry *state*, not just events | [`AsyncValue`](waiting.md) |
