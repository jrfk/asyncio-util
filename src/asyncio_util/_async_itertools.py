from __future__ import annotations

import asyncio
from typing import AsyncIterator, TypeVar

from asyncio_util._task_utils import cancel_tasks

T = TypeVar("T")


async def azip(
    *aiterables: AsyncIterator[T],
) -> AsyncIterator[tuple[T, ...]]:
    """Async zip: yield tuples from multiple async iterators in parallel.

    Stops when the shortest iterator is exhausted.
    Advances all iterators concurrently.
    """
    if not aiterables:
        return

    iters = [ai.__aiter__() for ai in aiterables]
    sentinel = object()

    while True:
        tasks = [asyncio.create_task(_anext(it, sentinel)) for it in iters]
        try:
            results = await asyncio.gather(*tasks)
        except BaseException:
            await cancel_tasks(tasks)
            raise

        if any(r is sentinel for r in results):
            return
        yield tuple(results)


async def azip_longest(
    *aiterables: AsyncIterator[T],
    fillvalue: T | None = None,
) -> AsyncIterator[tuple[T | None, ...]]:
    """Async zip_longest: yield tuples until all iterators are exhausted.

    Exhausted iterators are replaced with *fillvalue*.
    Advances all iterators concurrently.
    """
    if not aiterables:
        return

    iters = [ai.__aiter__() for ai in aiterables]
    sentinel = object()
    exhausted = [False] * len(iters)

    while True:
        tasks = []
        for i, it in enumerate(iters):
            if exhausted[i]:
                tasks.append(None)
            else:
                tasks.append(asyncio.create_task(_anext(it, sentinel)))

        active_tasks = [t for t in tasks if t is not None]
        try:
            if active_tasks:
                await asyncio.gather(*active_tasks)
        except BaseException:
            await cancel_tasks(active_tasks)
            raise

        results = []
        all_done = True
        for i, t in enumerate(tasks):
            if t is None:
                results.append(fillvalue)
            else:
                val = t.result()
                if val is sentinel:
                    exhausted[i] = True
                    results.append(fillvalue)
                else:
                    all_done = False
                    results.append(val)

        if all_done:
            return
        yield tuple(results)


async def _anext(ait: AsyncIterator[T], default: object) -> T | object:
    try:
        return await ait.__anext__()
    except StopAsyncIteration:
        return default
