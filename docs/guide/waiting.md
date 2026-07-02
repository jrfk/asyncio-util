# Waiting for values

`AsyncValue` distinguishes two kinds of waiting, borrowed from signal
processing:

- **Level** — "the value *is* X". If the condition already holds, you are
  done immediately. This is [`wait_value()`][asyncio_util.AsyncValue.wait_value].
- **Edge** — "the value *becomes* X". Only an actual change counts; the
  current value never matches. This is
  [`wait_transition()`][asyncio_util.AsyncValue.wait_transition].

## wait_value — level waiting

```python
av = AsyncValue("disconnected")

# Wait for a specific value:
await av.wait_value("connected")

# Or a predicate:
await av.wait_value(lambda state: state in ("connected", "degraded"))
```

`wait_value()` returns the **matched value**. If the current value already
matches, it returns immediately without suspending.

### The no-miss guarantee

Predicates are evaluated **synchronously inside the `value` setter**. The
matched value is captured at that instant and delivered to the waiter, even
if the value changes again before the waiting task gets scheduled:

```python
av = AsyncValue(10)

async def waiter():
    return await av.wait_value(20)

task = asyncio.ensure_future(waiter())
await asyncio.sleep(0)   # let the waiter register

av.value = 20   # match captured here
av.value = 10   # immediately flipped back

assert await task == 20    # the waiter still saw 20
assert av.value == 10      # even though the current value moved on
```

!!! warning "The returned value can be stale"
    Because of this capture semantics, the value returned by `wait_value()`
    is the value *that matched*, which is not necessarily the value *now*.
    Read `av.value` again if you need the current state.

## wait_transition — edge waiting

`wait_transition()` ignores the current state entirely and waits for the next
matching **change**. It returns a `(value, old_value)` pair:

```python
av = AsyncValue("disconnected")

# Any change at all:
value, old = await av.wait_transition()

# A change to a specific value:
value, old = await av.wait_transition("connected")

# A predicate over (new, old) — e.g. only rising edges:
value, old = await av.wait_transition(lambda new, old: new > old)
```

Edge predicates see both sides of the transition, which makes patterns like
"fire only when we *lose* the connection" one-liners:

```python
await av.wait_transition(
    lambda new, old: new == "disconnected" and old == "connected"
)
```

!!! note "Equal assignments are not transitions"
    `av.value = x` where `x == av.value` is a no-op. It wakes no waiter and
    produces no transition.

## held_for — debouncing

Sometimes a condition must be *stable* before you act on it: a sensor
reading, a health check, a connection state. Pass `held_for` to
`wait_value()` to require the match to hold continuously:

```python
# Only proceed once the connection has been up for 5 seconds straight.
await av.wait_value("connected", held_for=5.0)
```

If the condition is lost during the hold period, the timer restarts and the
wait continues. The call returns only after the predicate has held for at
least `held_for` seconds.

## Timeouts

`wait_value()` and `wait_transition()` take an optional `timeout` (seconds)
and raise `asyncio.TimeoutError` when it expires before a match:

```python
try:
    value = await av.wait_value(20, timeout=1.0)
except asyncio.TimeoutError:
    ...
```

The standard library timeout idioms work too, and are the way to bound the
iterator APIs:

=== "asyncio.wait_for (3.10+)"

    ```python
    value = await asyncio.wait_for(av.wait_value(20), timeout=1.0)
    ```

=== "asyncio.timeout (3.11+)"

    ```python
    async with asyncio.timeout(1.0):
        value = await av.wait_value(20)
    ```

Cancellation (from a timeout, `task.cancel()`, or a task group aborting) is
always safe: the internal waiter is removed in a `finally` block, so nothing
leaks no matter how the wait ends.

## Waiting from many tasks

Any number of tasks can wait on the same `AsyncValue` concurrently, with the
same or different conditions. Each waiter is independent; a single
assignment wakes every waiter whose condition it satisfies.

```python
results = await asyncio.gather(
    av.wait_value(7),
    av.wait_value(lambda v: v > 5),
    av.wait_transition(),
)
```

## Rules for predicates

- Predicates run inside the `value` setter, synchronously. Keep them
  **fast** and **side-effect free**.
- A predicate that raises delivers the exception to **its own waiter**: the
  `await` raises it. Other waiters and the assigning task are unaffected.
  Still: don't raise.
- Don't await inside predicates (they are plain functions, not coroutines).
- Any callable argument is treated as a predicate. If your values are
  themselves callables, wait with an explicit equality predicate:
  `av.wait_value(lambda v: v == target_fn)`.
