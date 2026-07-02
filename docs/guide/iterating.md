# Iterating over changes

Waiting once is `await`; reacting continuously is `async for`. `AsyncValue`
offers two async iterators with deliberately different semantics:

| | [`eventual_values()`][asyncio_util.AsyncValue.eventual_values] | [`transitions()`][asyncio_util.AsyncValue.transitions] |
| --- | --- | --- |
| Semantics | level — "what is the value" | edge — "what changed" |
| Yields | matching values | matching `(new, old)` pairs |
| Current value | yielded first (if matching) | never yielded |
| Slow consumer | skips ahead to the **latest** value | **misses** intermediate changes |
| Typical use | render state, sync to a target | log events, count edges |

## eventual_values — follow the state

`eventual_values()` yields the current value (if it matches) and then each
matching value as it changes. It is ideal when only the **latest** state
matters — UI rendering, reconciliation loops, watchdogs:

```python
async for state in connection_state.eventual_values():
    redraw_status_icon(state)
```

With a predicate or value, only matching states come through:

```python
async for _ in connection_state.eventual_values("disconnected"):
    schedule_reconnect()
```

### Exact semantics

- The same value is never yielded twice in a row.
- If the value changes while the loop body is running, intermediate values
  may be skipped, but the iterator **always converges to the latest matching
  value**. You cannot end up rendering a stale state forever.
- If a matching value is set while the iterator is *waiting* (not busy), it
  is captured and will be yielded even if the value immediately changes
  again — consistent with `wait_value()`'s no-miss guarantee.

```python
av = AsyncValue(0)

# Consumer busy while av.value goes 1, 2, 3, 4, 5...
# ...the next iteration yields 5. The 1-4 are skipped by design.
```

### Debouncing the stream: held_for

Like `wait_value()`, `eventual_values()` accepts `held_for`: a value is only
yielded once it has matched continuously for that many seconds. Values that
flicker in and out of the predicate within the hold period are skipped:

```python
# Only see readings that stayed over the threshold for 2 seconds.
async for reading in sensor.eventual_values(lambda v: v > 100, held_for=2.0):
    trigger_alarm(reading)
```

## transitions — follow the changes

`transitions()` yields `(value, old_value)` for each matching change. Use it
when the *event* matters, not just the resulting state:

```python
async for new, old in av.transitions(lambda new, old: new < old):
    logger.warning("value dropped from %s to %s", old, new)
```

### Missed transitions

`transitions()` reports edges **only while it is actually waiting**. A change
that happens while your loop body is still processing the previous one is
gone — edges are not queued:

```python
async for new, old in av.transitions():
    await slow_handler(new)   # a change during this await is missed
```

!!! warning "If every edge matters, use a queue"
    This is inherent to the "current state" model — an `AsyncValue` stores
    one value, not a history. When you must process *every* change, push
    them into an `asyncio.Queue` at the producer side:

    ```python
    queue: asyncio.Queue[int] = asyncio.Queue()

    def set_value(v: int) -> None:
        av.value = v
        queue.put_nowait(v)   # explicit history
    ```

## Ending iteration

Both iterators are infinite. End them the way you end any async iteration:

- `break` out of the loop,
- cancel the consuming task, or
- wrap the loop with a timeout scope.

Cleanup is automatic in all cases — waiters are removed the moment the
iterator is suspended, closed, or its task is cancelled.

```python
async def watch(av: AsyncValue[str]) -> None:
    async for state in av.eventual_values():
        if state == "shutdown":
            break
        await apply(state)
```
