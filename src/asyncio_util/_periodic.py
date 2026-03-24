from __future__ import annotations

import asyncio
from typing import AsyncIterator


async def periodic(period: float) -> AsyncIterator[tuple[float, float | None]]:
    """Yield (elapsed, delta) tuples at regular intervals.

    Args:
        period: Interval in seconds between iterations.

    Yields:
        A tuple of (elapsed_since_start, delta_since_last).
        delta is None on the first iteration.

    If the loop body takes longer than *period*, the next iteration
    starts immediately without sleeping.
    """
    if period <= 0:
        raise ValueError(f"period must be positive, got {period}")
    loop = asyncio.get_running_loop()
    t0 = loop.time()
    t_last: float | None = None
    t_start = t0

    while True:
        delta = t_start - t_last if t_last is not None else None
        yield (t_start - t0, delta)

        target = t_start + period
        now = loop.time()
        delay = target - now
        if delay > 0:
            await asyncio.sleep(delay)
        else:
            await asyncio.sleep(0)

        t_last = t_start
        t_start = loop.time()
