import asyncio

import pytest

from asyncio_util import MulticastQueue


@pytest.mark.asyncio
async def test_single_listener():
    mq = MulticastQueue()
    received = []

    async with mq.listen() as q:
        await mq.broadcast("hello")
        await mq.broadcast("world")
        received.append(await q.get())
        received.append(await q.get())

    assert received == ["hello", "world"]


@pytest.mark.asyncio
async def test_multiple_listeners():
    mq = MulticastQueue()
    results_a = []
    results_b = []

    async with mq.listen() as qa, mq.listen() as qb:
        await mq.broadcast(42)

        results_a.append(await qa.get())
        results_b.append(await qb.get())

    assert results_a == [42]
    assert results_b == [42]


@pytest.mark.asyncio
async def test_async_iteration():
    mq = MulticastQueue()
    received = []

    async def listener():
        async with mq.listen() as q:
            async for item in q:
                received.append(item)

    task = asyncio.create_task(listener())
    await asyncio.sleep(0.02)

    await mq.broadcast("a")
    await mq.broadcast("b")
    await asyncio.sleep(0.02)

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    assert received == ["a", "b"]


@pytest.mark.asyncio
async def test_listener_cleanup():
    mq = MulticastQueue()

    async with mq.listen():
        assert len(mq._listeners) == 1

    assert len(mq._listeners) == 0
