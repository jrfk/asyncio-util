"""Regression tests for wait_value(held_for=) and eventual_values(held_for=).

wait_value(..., held_for=N) previously raised TimeoutError when the value
*successfully* held for N seconds, and eventual_values(..., held_for=N) had
the hold logic inverted.
"""

import asyncio

import pytest

from asyncio_util import AsyncValue


@pytest.mark.asyncio
async def test_wait_value_held_for_returns_after_stable_hold():
    value = AsyncValue(0)

    async def set_value_later():
        await asyncio.sleep(0.05)
        value.value = 10

    asyncio.create_task(set_value_later())
    result = await asyncio.wait_for(
        value.wait_value(lambda v: v > 5, held_for=0.1), timeout=1
    )
    assert result == 10


@pytest.mark.asyncio
async def test_wait_value_held_for_immediately_matching_value():
    value = AsyncValue(10)
    result = await asyncio.wait_for(
        value.wait_value(lambda v: v > 5, held_for=0.05), timeout=1
    )
    assert result == 10


@pytest.mark.asyncio
async def test_wait_value_held_for_restarts_on_flicker():
    value = AsyncValue(0)
    loop = asyncio.get_running_loop()
    start = loop.time()

    async def flicker():
        value.value = 10  # match
        await asyncio.sleep(0.05)
        value.value = 0  # lost before 0.1s elapsed
        await asyncio.sleep(0.01)
        value.value = 10  # match again; hold restarts

    task = asyncio.create_task(flicker())
    result = await asyncio.wait_for(
        value.wait_value(lambda v: v > 5, held_for=0.1), timeout=1
    )
    assert result == 10
    assert loop.time() - start >= 0.15
    await task


@pytest.mark.asyncio
async def test_wait_value_held_for_with_timeout_still_times_out():
    value = AsyncValue(0)
    with pytest.raises(asyncio.TimeoutError):
        await value.wait_value(lambda v: v > 5, held_for=0.05, timeout=0.05)


@pytest.mark.asyncio
async def test_eventual_values_held_for_yields_only_stable_values():
    value = AsyncValue(0)
    seen = []

    async def consume():
        async for v in value.eventual_values(lambda v: v > 5, held_for=0.08):
            seen.append(v)
            if v == 30:
                break

    async def produce():
        value.value = 10  # flickers away quickly: must not be yielded
        await asyncio.sleep(0.02)
        value.value = 0
        await asyncio.sleep(0.02)
        value.value = 30  # stays: must be yielded
    consumer = asyncio.create_task(consume())
    await asyncio.sleep(0)
    producer = asyncio.create_task(produce())
    await asyncio.wait_for(asyncio.gather(consumer, producer), timeout=1)
    assert seen == [30]


@pytest.mark.asyncio
async def test_eventual_values_held_for_initial_stable_value():
    value = AsyncValue(10)
    iterator = value.eventual_values(lambda v: v > 5, held_for=0.05)
    first = await asyncio.wait_for(anext(iterator), timeout=1)
    assert first == 10
    await iterator.aclose()
