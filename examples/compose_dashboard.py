"""Combine several AsyncValues and await a cross-value condition.

A robot may start a job only when it is docked AND sufficiently
charged.  compose_values() turns that into a single predicate.

Run:  python examples/compose_dashboard.py
"""

import asyncio

from asyncio_util import AsyncValue, compose_values


async def charger(battery: AsyncValue[int]) -> None:
    while battery.value < 100:
        await asyncio.sleep(0.1)
        battery.value = min(100, battery.value + 25)
        print(f"[charger] battery = {battery.value}%")


async def driver(docked: AsyncValue[bool]) -> None:
    await asyncio.sleep(0.25)
    docked.value = True
    print("[driver] docked")


async def wait_ready(status) -> None:
    snapshot = await status.wait_value(lambda s: s.docked and s.battery >= 75)
    print(f"[main] ready to start job: {snapshot}")


async def main() -> None:
    docked = AsyncValue(False)
    battery = AsyncValue(10)

    with compose_values(docked=docked, battery=battery) as status:
        await asyncio.gather(
            charger(battery),
            driver(docked),
            wait_ready(status),
        )


if __name__ == "__main__":
    asyncio.run(main())
