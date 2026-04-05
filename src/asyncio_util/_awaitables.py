from __future__ import annotations

import asyncio
from collections import namedtuple
from typing import Any, Awaitable, Callable

from asyncio_util._task_utils import cancel_tasks


async def wait_any(*args: Callable[[], Awaitable[Any]]) -> None:
    """Run async callables concurrently, return when the first completes.

    All remaining tasks are cancelled after the first one finishes.

    Args:
        *args: Zero-argument async callables.
    """
    if not args:
        return

    tasks = [asyncio.create_task(f()) for f in args]
    try:
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        await cancel_tasks(pending)
        errors = []
        for task in done:
            try:
                task.result()
            except BaseException as e:
                errors.append(e)
        if errors:
            raise errors[0]
    except BaseException:
        await cancel_tasks(tasks)
        raise


async def wait_all(*args: Callable[[], Awaitable[Any]]) -> None:
    """Run async callables concurrently, return when all complete.

    If any task raises, all remaining tasks are cancelled and
    the first exception is re-raised.

    Args:
        *args: Zero-argument async callables.
    """
    if not args:
        return

    tasks = [asyncio.create_task(f()) for f in args]
    try:
        await asyncio.gather(*tasks)
    except BaseException:
        await cancel_tasks(tasks)
        raise


async def wait_any_map(
    *fns: Callable[[], Awaitable[Any]],
    **fn_map: Callable[[], Awaitable[Any]],
) -> Any:
    """Like :func:`wait_any`, but captures return values from named callables.

    Positional callables are fire-and-forget (return values discarded).
    Keyword callables have their return values captured in a namedtuple.

    Returns:
        A namedtuple with fields matching the keyword argument names.
        Fields for callables that did not finish first are None.

    Usage::

        result = await wait_any_map(
            timeout=lambda: asyncio.sleep(5),
            value=lambda: some_value.wait_value(predicate),
        )
        if result.value is not None:
            process(result.value)
    """
    if not fns and not fn_map:
        return None

    field_names = list(fn_map.keys())
    if field_names:
        result_type = namedtuple("WaitAnyResults", field_names)  # type: ignore[misc]
        results: dict[str, Any] = {name: None for name in field_names}
    else:
        result_type = None
        results = {}

    all_tasks: list[asyncio.Task[Any]] = []
    task_to_name: dict[asyncio.Task[Any], str | None] = {}

    for f in fns:
        task = asyncio.create_task(f())
        all_tasks.append(task)
        task_to_name[task] = None

    for name, f in fn_map.items():
        task = asyncio.create_task(f())
        all_tasks.append(task)
        task_to_name[task] = name

    try:
        done, pending = await asyncio.wait(
            all_tasks, return_when=asyncio.FIRST_COMPLETED
        )
        await cancel_tasks(pending)

        for task in done:
            name = task_to_name[task]
            if name is not None:
                results[name] = task.result()
            else:
                task.result()

    except BaseException:
        await cancel_tasks(all_tasks)
        raise

    if result_type is not None:
        return result_type(**results)
    return None
