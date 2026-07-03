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

    Iterations are scheduled on the absolute ``start + k * period``
    grid, so per-iteration latency does not accumulate as drift.  If
    the loop body takes longer than *period*, the next iteration starts
    (almost) immediately at the next free grid slot; missed slots are
    skipped, not queued.
    """
    if period <= 0:
        raise ValueError(f"period must be positive, got {period}")
    loop = asyncio.get_running_loop()
    t0 = loop.time()
    t_last: float | None = None
    t_start = t0
    tick = 1

    while True:
        delta = t_start - t_last if t_last is not None else None
        yield (t_start - t0, delta)

        now = loop.time()
        target = t0 + tick * period
        while target <= now:  # overran one or more slots: skip them
            tick += 1
            target = t0 + tick * period
        await asyncio.sleep(target - now)
        tick += 1

        t_last = t_start
        t_start = loop.time()
