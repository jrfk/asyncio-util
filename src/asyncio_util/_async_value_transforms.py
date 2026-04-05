from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from asyncio_util._async_bool import AsyncBool
from asyncio_util._async_value import AsyncValue


@asynccontextmanager
async def open_held_for(
    src: AsyncValue[Any], *, duration: float
) -> AsyncIterator[AsyncBool]:
    """Track whether *src* has been unchanged for *duration* seconds.

    Yields an :class:`AsyncBool` that becomes True when *src* has not
    changed for *duration* seconds, and resets to False on any change.

    Args:
        src: The source value to monitor.
        duration: Seconds the value must remain stable.
    """
    output = AsyncBool(False)

    async def _listener() -> None:
        last_value = src.value
        while True:
            try:
                await asyncio.wait_for(
                    src.wait_value(lambda v: v != last_value), timeout=duration
                )
                # Value changed before duration elapsed
                output.value = False
                last_value = src.value
            except asyncio.TimeoutError:
                # Value held for the full duration
                output.value = True
                last_value = src.value
                await src.wait_value(lambda v: v != last_value)
                output.value = False
                last_value = src.value

    task = asyncio.create_task(_listener())
    try:
        yield output
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


@asynccontextmanager
async def open_hysteresis(
    src: AsyncValue[bool],
    *,
    rising_duration: float = 0,
    falling_duration: float = 0,
) -> AsyncIterator[AsyncBool]:
    """Apply hysteresis filtering to a boolean source.

    The output transitions from False to True only after *src* has
    been True for *rising_duration* seconds, and from True to False
    only after *src* has been False for *falling_duration* seconds.

    Args:
        src: Boolean source value to filter.
        rising_duration: Seconds *src* must stay True before output rises.
        falling_duration: Seconds *src* must stay False before output falls.
    """
    output = AsyncBool(src.value)

    async def _listener() -> None:
        while True:
            anticipated = not output.value
            duration = rising_duration if anticipated else falling_duration

            await src.wait_value(anticipated)

            if duration > 0:
                try:
                    await asyncio.wait_for(
                        src.wait_value(not anticipated), timeout=duration
                    )
                    # Value flipped back before duration elapsed
                    continue
                except asyncio.TimeoutError:
                    pass

            output.value = anticipated

    task = asyncio.create_task(_listener())
    try:
        yield output
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
