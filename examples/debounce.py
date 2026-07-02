"""Debounce a flapping sensor with wait_value(..., held_for=N).

The reading briefly spikes over the threshold, drops back, then stays
high.  The waiter only fires for the stable period.

Run:  python examples/debounce.py
"""

import asyncio

from asyncio_util import AsyncValue


async def sensor(reading: AsyncValue[float]) -> None:
    for value, delay in ((105.0, 0.1), (95.0, 0.1), (110.0, 0.5)):
        await asyncio.sleep(delay)
        print(f"[sensor] reading = {value}")
        reading.value = value


async def alarm(reading: AsyncValue[float]) -> None:
    value = await reading.wait_value(lambda v: v > 100.0, held_for=0.3)
    print(f"[alarm] over 100 for 0.3s straight (value={value})")


async def main() -> None:
    reading = AsyncValue(90.0)
    await asyncio.gather(alarm(reading), sensor(reading))


if __name__ == "__main__":
    asyncio.run(main())
