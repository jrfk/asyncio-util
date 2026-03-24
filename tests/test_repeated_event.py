import asyncio

import pytest

from asyncio_util import RepeatedEvent


@pytest.mark.asyncio
async def test_set_and_wait():
    event = RepeatedEvent()

    async def set_later():
        await asyncio.sleep(0.05)
        event.set()

    asyncio.create_task(set_later())
    await event.wait()


@pytest.mark.asyncio
async def test_multiple_sets():
    event = RepeatedEvent()
    count = 0

    async def listener():
        nonlocal count
        async for _ in event.unqueued_events():
            count += 1
            if count >= 3:
                break

    task = asyncio.create_task(listener())

    for _ in range(3):
        await asyncio.sleep(0.05)
        event.set()

    await asyncio.wait_for(task, timeout=1.0)
    assert count == 3


@pytest.mark.asyncio
async def test_events_eventual_consistency():
    event = RepeatedEvent()
    received = []

    async def listener():
        async for _ in event.events():
            received.append(True)
            if len(received) >= 2:
                break

    task = asyncio.create_task(listener())
    await asyncio.sleep(0.02)

    event.set()
    await asyncio.sleep(0.05)
    event.set()

    await asyncio.wait_for(task, timeout=1.0)
    assert len(received) == 2


@pytest.mark.asyncio
async def test_events_repeat_last():
    event = RepeatedEvent()
    event.set()  # Fire before listener starts
    received = []

    async def listener():
        async for _ in event.events(repeat_last=True):
            received.append(True)
            if len(received) >= 1:
                break

    task = asyncio.create_task(listener())
    await asyncio.wait_for(task, timeout=1.0)
    assert len(received) == 1
