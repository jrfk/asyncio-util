from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Awaitable, Callable


class CancelScope:
    """Lightweight cancel scope for move_on_when.

    Attributes:
        cancelled_caught: True if the body was cancelled by the
            trigger completing (not by an external cancellation).
    """

    def __init__(self):
        self.cancelled_caught: bool = False
        self._should_cancel: bool = False


class _MoveOnWhen:
    """Async context manager that cancels the body when a trigger completes.

    Note:
        If the trigger fires at the same moment that the task is
        cancelled externally, the external cancellation may be
        mistakenly treated as trigger-initiated. This is a known
        limitation of asyncio's cancellation model (unlike trio's
        ``CancelScope`` which resolves this at the runtime level).
    """

    def __init__(
        self,
        fn: Callable[..., Awaitable[Any]],
        *args: Any,
        **kwargs: Any,
    ):
        self._fn = fn
        self._args = args
        self._kwargs = kwargs
        self.scope = CancelScope()
        self._trigger_task: asyncio.Task[None] | None = None

    async def __aenter__(self) -> CancelScope:
        current_task = asyncio.current_task()
        scope = self.scope

        async def _run_trigger() -> None:
            try:
                await self._fn(*self._args, **self._kwargs)
            except asyncio.CancelledError:
                return
            scope._should_cancel = True
            if current_task is not None and not current_task.done():
                current_task.cancel()

        self._trigger_task = asyncio.create_task(_run_trigger())
        await asyncio.sleep(0)  # Let the trigger task start running
        return self.scope

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        trigger_task = self._trigger_task
        if trigger_task is not None:
            if not trigger_task.done():
                trigger_task.cancel()
                try:
                    await trigger_task
                except asyncio.CancelledError:
                    pass
                except Exception:
                    pass
            else:
                # Retrieve result to avoid "Task exception was never retrieved"
                try:
                    trigger_task.result()
                except asyncio.CancelledError:
                    pass
                except Exception:
                    pass

        if exc_type is asyncio.CancelledError and self.scope._should_cancel:
            self.scope.cancelled_caught = True
            return True  # Suppress the CancelledError

        return False


def move_on_when(
    fn: Callable[..., Awaitable[Any]],
    *args: Any,
    **kwargs: Any,
) -> _MoveOnWhen:
    """Cancel the body when *fn* completes.

    Usage::

        async with move_on_when(event.wait) as scope:
            await long_running_work()
        if scope.cancelled_caught:
            print("interrupted by event")

    Args:
        fn: Async callable whose completion triggers cancellation.
        *args: Positional arguments forwarded to *fn*.
        **kwargs: Keyword arguments forwarded to *fn*.

    Returns:
        An async context manager yielding a :class:`CancelScope` whose
        ``cancelled_caught`` attribute indicates whether the body was
        interrupted.
    """
    return _MoveOnWhen(fn, *args, **kwargs)


@asynccontextmanager
async def run_and_cancelling(
    fn: Callable[..., Awaitable[Any]],
    *args: Any,
    **kwargs: Any,
) -> AsyncIterator[None]:
    """Run *fn* in the background and cancel it when the body exits.

    Usage::

        async with run_and_cancelling(background_worker, arg1):
            await do_main_work()
        # background_worker is cancelled here

    Args:
        fn: Async callable to run in the background.
        *args: Positional arguments forwarded to *fn*.
        **kwargs: Keyword arguments forwarded to *fn*.
    """
    task = asyncio.create_task(fn(*args, **kwargs))
    try:
        yield
    finally:
        if task.done():
            # Propagate non-cancellation exceptions from the background task
            try:
                task.result()
            except asyncio.CancelledError:
                pass
            except Exception:
                raise
        else:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


@asynccontextmanager
async def start_and_cancelling(
    fn: Callable[..., Awaitable[Any]],
    *args: Any,
    **kwargs: Any,
) -> AsyncIterator[None]:
    """Run *fn* in the background, wait for it to signal readiness, then
    cancel it when the body exits.

    The callable *fn* must accept a keyword argument ``task_status``
    and call ``task_status.set()`` when it is ready.

    Usage::

        async def server(*, task_status):
            listener = await setup_listener()
            task_status.set()  # signal ready
            await serve_forever(listener)

        async with start_and_cancelling(server):
            await use_server()

    Args:
        fn: Async callable that accepts ``task_status`` keyword.
        *args: Positional arguments forwarded to *fn*.
        **kwargs: Keyword arguments forwarded to *fn*.
    """
    started = asyncio.Event()

    class _TaskStatus:
        def set(self) -> None:
            started.set()

    task_status = _TaskStatus()
    task = asyncio.create_task(fn(*args, task_status=task_status, **kwargs))

    # If the task fails before calling task_status.set(), unblock started.wait()
    task.add_done_callback(lambda _: started.set())

    try:
        await started.wait()

        if task.done():
            task.result()  # Propagate exception if task failed before started

        yield
    finally:
        if task.done():
            try:
                task.result()
            except asyncio.CancelledError:
                pass
            except Exception:
                raise
        else:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
