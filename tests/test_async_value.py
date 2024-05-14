# ruff: noqa
import asyncio

import pytest

from asyncio_util._async_value import AsyncValue


@pytest.mark.asyncio
async def test_wait_value():
    value = AsyncValue(10)

    async def set_value_later():
        await asyncio.sleep(0.1)
        value.value = 20

    asyncio.create_task(set_value_later())
    result = await value.wait_value(20)
    assert result == 20


@pytest.mark.asyncio
async def test_wait_value_predicate():
    value = AsyncValue(10)

    async def set_value_later():
        await asyncio.sleep(0.1)
        value.value = 25

    asyncio.create_task(set_value_later())
    result = await value.wait_value(lambda v: v > 20)
    assert result == 25


@pytest.mark.asyncio
async def test_wait_value_timeout():
    value = AsyncValue(10)

    async def set_value_later():
        await asyncio.sleep(2)
        value.value = 20

    asyncio.create_task(set_value_later())
    with pytest.raises(asyncio.TimeoutError, match="Operation timed out"):
        await value.wait_value(20, timeout=0.1)


@pytest.mark.asyncio
async def test_eventual_values():
    value = AsyncValue(10)

    async def set_values():
        await asyncio.sleep(0.1)
        value.value = 20
        await asyncio.sleep(0.1)
        value.value = 30

    asyncio.create_task(set_values())
    results = []
    async for v in value.eventual_values(lambda v: v > 10):
        results.append(v)
        if len(results) == 2:
            break
    assert results == [20, 30]


@pytest.mark.asyncio
async def test_wait_transition():
    value = AsyncValue(10)

    async def set_value_later():
        await asyncio.sleep(0.1)
        value.value = 20

    asyncio.create_task(set_value_later())
    new_value, old_value = await value.wait_transition(
        lambda v, old: v == 20 and old == 10
    )
    assert new_value == 20
    assert old_value == 10


@pytest.mark.asyncio
async def test_wait_transition_timeout():
    value = AsyncValue(10)

    async def set_value_later():
        await asyncio.sleep(0.2)
        value.value = 20

    asyncio.create_task(set_value_later())
    with pytest.raises(asyncio.TimeoutError, match="Operation timed out"):
        await value.wait_transition(lambda v, old: v == 20 and old == 10, timeout=0.1)


@pytest.mark.asyncio
async def test_transitions():
    value = AsyncValue(10)

    async def set_values():
        await asyncio.sleep(0.1)
        value.value = 20
        await asyncio.sleep(0.1)
        value.value = 30

    asyncio.create_task(set_values())
    results = []
    async for new_value, old_value in value.transitions(lambda v, old: v > old):
        results.append((new_value, old_value))
        if len(results) == 2:
            break
    assert results == [(20, 10), (30, 20)]


@pytest.mark.asyncio
async def test_open_transform():
    value = AsyncValue(10)

    async with value.open_transform(lambda v: v * 2) as transformed_value:
        assert transformed_value.value == 20
        value.value = 15
        assert transformed_value.value == 30


@pytest.mark.asyncio
async def test_open_transform_cleanup():
    value = AsyncValue(10)

    async with value.open_transform(lambda v: v * 2) as transformed_value:
        assert transformed_value.value == 20
        value.value = 15
        assert transformed_value.value == 30

    value.value = 20
    async with value.open_transform(lambda v: v * 2) as transformed_value:
        assert transformed_value.value == 40
