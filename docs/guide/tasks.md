# Tasks and cancellation

asyncio gives you `create_task`, `gather` and `wait` — powerful, but easy to
leak tasks with. These helpers wrap the common patterns in *structured* form:
every task they start is cancelled and awaited before control returns to you.

All of them take **zero-argument async callables** (not coroutine objects),
so pass `functools.partial` or a `lambda` when you need arguments:

```python
from functools import partial

await wait_any(partial(fetch, url1), partial(fetch, url2))
```

## wait_any — first one wins

[`wait_any()`][asyncio_util.wait_any] runs the callables concurrently and
returns when the **first** completes. Everything still running is cancelled
and awaited:

```python
from asyncio_util import wait_any

await wait_any(
    lambda: user_pressed_cancel.wait_value(True),
    lambda: job.wait_value("done"),
)
```

If the winner raised, that exception propagates.

## wait_all — everyone finishes

[`wait_all()`][asyncio_util.wait_all] returns when **all** callables have
completed. If any raises, the rest are cancelled and the exception
propagates:

```python
from asyncio_util import wait_all

await wait_all(sync_database, sync_cache, sync_search_index)
```

## wait_any_map — which one won, and with what?

[`wait_any_map()`][asyncio_util.wait_any_map] is `wait_any` for when you need
to know *which* branch finished and what it returned. Keyword arguments name
the branches; the result is a namedtuple where only the finished branch is
non-`None`:

```python
from asyncio_util import wait_any_map

result = await wait_any_map(
    timeout=lambda: asyncio.sleep(5),
    value=lambda: av.wait_value(lambda v: v > 10),
)
if result.value is not None:
    process(result.value)
else:
    print("timed out")
```

## move_on_when — cancel a block on a signal

[`move_on_when()`][asyncio_util.move_on_when] runs a block until a *trigger*
coroutine completes, then cancels the block. Where `asyncio.timeout()`
bounds a block by time, `move_on_when` bounds it by an **event**:

```python
from asyncio_util import move_on_when

async with move_on_when(shutdown_requested.wait_value, True) as scope:
    await serve_forever()

if scope.cancelled_caught:
    print("interrupted by shutdown request")
```

- The yielded [`CancelScope`][asyncio_util.CancelScope] records whether the
  body was interrupted by the trigger (`cancelled_caught`) as opposed to
  finishing on its own.
- The trigger starts running once the body reaches its first `await`.
- If the trigger itself raises, the body is cancelled and the trigger's
  exception is re-raised from the block.

!!! warning "asyncio limitation"
    If the trigger fires at the same moment the surrounding task is
    cancelled from outside, the external cancellation can be
    indistinguishable from the trigger's and may be swallowed. This is
    inherent to asyncio's single-flavor cancellation (trio solves it with
    runtime-level cancel scopes). Keep `move_on_when` bodies small.

## run_and_cancelling — a background task scoped to a block

[`run_and_cancelling()`][asyncio_util.run_and_cancelling] runs a background
task for exactly as long as the block is executing — the inverse of
`move_on_when`:

```python
from asyncio_util import run_and_cancelling

async with run_and_cancelling(heartbeat, interval=1.0):
    await do_migration()
# heartbeat is cancelled and awaited here
```

If the background task fails while the body runs, the body is not
interrupted; the failure is re-raised when the block exits (the body's own
exception, if any, takes precedence).

## start_and_cancelling — wait until the task is ready

[`start_and_cancelling()`][asyncio_util.start_and_cancelling] is
`run_and_cancelling` for background tasks that need a startup phase. The
callable receives a `task_status` keyword and calls `task_status.set()` when
it is ready; the block body does not start until then:

```python
from asyncio_util import start_and_cancelling

async def server(*, task_status):
    listener = await create_listener()
    task_status.set()          # ready — the body may proceed
    await serve(listener)

async with start_and_cancelling(server):
    await run_client_tests()   # the server is guaranteed to be listening
```

If the task fails before signaling readiness, the exception is raised
immediately instead of entering the block.

## Choosing between them

| You want to… | Reach for |
| --- | --- |
| race several operations | `wait_any` / `wait_any_map` |
| run several operations to completion | `wait_all` |
| stop work when an event fires | `move_on_when` |
| stop work after a duration | `asyncio.timeout()` (stdlib) |
| keep a helper task alive during a block | `run_and_cancelling` |
| …and wait for it to boot first | `start_and_cancelling` |
