# Deriving and composing

Real systems rarely watch one raw value. They watch *functions* of values
("is the temperature in °F above 100?") and *combinations* of values ("is the
robot docked **and** charged?"). `asyncio-util` covers both, plus two
time-based filters for flappy signals.

## open_transform — derive one value from another

[`open_transform()`][asyncio_util.AsyncValue.open_transform] gives you a new
`AsyncValue` that always equals `f(source.value)`:

```python
celsius = AsyncValue(25.0)

async with celsius.open_transform(lambda c: c * 9 / 5 + 32) as fahrenheit:
    assert fahrenheit.value == 77.0

    # The derived value is a full AsyncValue — await it, iterate it:
    await fahrenheit.wait_value(lambda f: f > 100)
```

Key properties:

- Updates are **synchronous**: by the time `celsius.value = x` returns,
  `fahrenheit.value` is already `f(x)`. There is no window where the two
  disagree.
- Updates are **deduplicated** through the derived value's own setter. If
  `f` maps two inputs to the same output, the derived value does not
  produce a transition:

    ```python
    parity = AsyncValue(1)
    async with parity.open_transform(lambda x: x % 2) as is_odd:
        parity.value = 3   # 1 -> 3, but 3 % 2 == 1: no change on is_odd
    ```

- Two `open_transform` calls with the **same function object** share one
  derived value (reference-counted internally).
- Leaving the `async with` block disconnects the derived value. It keeps its
  last value but no longer follows the source.

!!! note "Transform functions"
    Like predicates, transform functions run inside the source's setter:
    keep them fast, pure, and non-raising. If one does raise, the exception
    propagates to the code assigning `value` — after all other waiters have
    been notified.

## compose_values — combine several values

[`compose_values()`][asyncio_util.compose_values] merges any number of
`AsyncValue`s into one whose value is a **named tuple**, updated whenever any
input changes:

```python
from asyncio_util import AsyncValue, compose_values

docked = AsyncValue(False)
battery_percent = AsyncValue(15)

with compose_values(docked=docked, battery=battery_percent) as status:
    # status.value is a namedtuple: (docked=False, battery=15)
    print(status.value.docked, status.value.battery)

    # Await a condition that spans both:
    await status.wait_value(lambda s: s.docked and s.battery >= 90)
```

This is the clean answer to "wait until A **and** B": no manual event
choreography, no re-check loops — one predicate over one composite value.

Pass `_transform_` to map the composite tuple to something else in one step:

```python
with compose_values(_transform_=lambda s: s.x + s.y, x=x, y=y) as total:
    await total.wait_value(lambda t: t > 100)
```

Everything from the previous chapters applies to the composite, because it
*is* an `AsyncValue`:

```python
# React to any change of either input:
async for snapshot in status.eventual_values():
    update_dashboard(snapshot)

# Edge-detect on the combination:
await status.wait_transition(
    lambda new, old: new.docked and not old.docked
)
```

## AsyncBool — boolean shorthand

[`AsyncBool`][asyncio_util.AsyncBool] is simply `AsyncValue[bool]` with a
`False` default — handy for flags:

```python
from asyncio_util import AsyncBool

ready = AsyncBool()          # starts False
await ready.wait_value(True)
```

(For trio-util compatibility, `BoolEvent` and `ValueEvent` are provided as
aliases of `AsyncBool` and `AsyncValue`.)

## open_held_for — "has it been stable?"

[`open_held_for()`][asyncio_util.open_held_for] watches *any* `AsyncValue`
and yields an `AsyncBool` that is True while the source has not changed for
`duration` seconds:

```python
from asyncio_util import AsyncValue, open_held_for

position = AsyncValue((0.0, 0.0))

async with open_held_for(position, duration=2.0) as settled:
    await settled.wait_value(True)
    print("position has been stable for 2 seconds")
```

Any change of the source resets the output to False and restarts the timer.

## open_hysteresis — de-flap a boolean

[`open_hysteresis()`][asyncio_util.open_hysteresis] filters a boolean
`AsyncValue` so that short blips don't propagate: the output only rises after
the input has been True for `rising_duration`, and only falls after it has
been False for `falling_duration`:

```python
from asyncio_util import AsyncBool, open_hysteresis

link_up = AsyncBool()

async with open_hysteresis(link_up, rising_duration=1.0,
                           falling_duration=5.0) as stable_link:
    async for is_up, _ in stable_link.transitions():
        print("link", "recovered" if is_up else "LOST")
```

A 200 ms network blip never reaches `stable_link`.

!!! note "Background tasks"
    `open_held_for` and `open_hysteresis` run a small background task while
    the `async with` block is open; it is cancelled and awaited on exit.

## Choosing between them

| You want to… | Reach for |
| --- | --- |
| watch `f(value)` of one source | `open_transform` |
| await a condition across several sources | `compose_values` |
| both — e.g. `f(a, b)` | `compose_values` with `_transform_` |
| know when a value has settled | `open_held_for` |
| suppress short blips of a flag | `open_hysteresis` |
