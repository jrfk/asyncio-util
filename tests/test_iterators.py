import asyncio

import pytest

from asyncio_util import iter_fail_after, iter_move_on_after


async def slow_range(n, delay=0.05):
    for i in range(n):
        await asyncio.sleep(delay)
        yield i


async def fast_range(n):
    for i in range(n):
        await asyncio.sleep(0)
        yield i


@pytest.mark.asyncio
async def test_iter_move_on_after_completes():
    results = []
    async for item in iter_move_on_after(1.0, fast_range(3)):
        results.append(item)
    assert results == [0, 1, 2]


@pytest.mark.asyncio
async def test_iter_move_on_after_stops():
    results = []
    async for item in iter_move_on_after(0.03, slow_range(10, delay=0.05)):
        results.append(item)
    # Should stop after timeout, getting 0 or possibly 1 item
    assert len(results) <= 1


@pytest.mark.asyncio
async def test_iter_fail_after_completes():
    results = []
    async for item in iter_fail_after(1.0, fast_range(3)):
        results.append(item)
    assert results == [0, 1, 2]


@pytest.mark.asyncio
async def test_iter_fail_after_raises():
    with pytest.raises(asyncio.TimeoutError):
        async for _ in iter_fail_after(0.03, slow_range(10, delay=0.05)):
            pass
