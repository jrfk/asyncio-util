"""Wait for states and observe transitions of a connection state machine.

Run:  python examples/connection_state.py
"""

import asyncio

from asyncio_util import AsyncValue


async def connect(state: AsyncValue[str]) -> None:
    for next_state in ("connecting", "connected", "degraded", "connected"):
        await asyncio.sleep(0.2)
        print(f"[producer] -> {next_state}")
        state.value = next_state


async def wait_until_connected(state: AsyncValue[str]) -> None:
    value = await state.wait_value("connected")
    print(f"[wait_value] connected (value={value!r})")


async def log_every_transition(state: AsyncValue[str]) -> None:
    async for new, old in state.transitions():
        print(f"[transitions] {old!r} -> {new!r}")
        if new == "connected" and old == "degraded":
            print("[transitions] recovered, stopping log")
            return


async def main() -> None:
    state = AsyncValue("disconnected")
    await asyncio.gather(
        wait_until_connected(state),
        log_every_transition(state),
        connect(state),
    )


if __name__ == "__main__":
    asyncio.run(main())
