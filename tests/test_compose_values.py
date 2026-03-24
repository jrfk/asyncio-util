import asyncio

import pytest

from asyncio_util import AsyncValue, compose_values


@pytest.mark.asyncio
async def test_compose_basic():
    x = AsyncValue(1)
    y = AsyncValue(2)

    with compose_values(x=x, y=y) as composite:
        assert composite.value.x == 1
        assert composite.value.y == 2

        x.value = 10
        assert composite.value.x == 10
        assert composite.value.y == 2


@pytest.mark.asyncio
async def test_compose_with_transform():
    x = AsyncValue(3)
    y = AsyncValue(4)

    with compose_values(_transform_=lambda v: v.x + v.y, x=x, y=y) as total:
        assert total.value == 7

        x.value = 10
        assert total.value == 14


@pytest.mark.asyncio
async def test_compose_wait_value():
    x = AsyncValue(0)
    y = AsyncValue(0)

    with compose_values(_transform_=lambda v: v.x + v.y, x=x, y=y) as total:

        async def update_later():
            await asyncio.sleep(0.05)
            x.value = 50

        asyncio.create_task(update_later())
        result = await total.wait_value(lambda v: v >= 50)
        assert result == 50


@pytest.mark.asyncio
async def test_compose_cleanup():
    x = AsyncValue(1)

    with compose_values(x=x) as composite:
        assert composite.value.x == 1

    # After exiting context, changes to x should not affect composite
    x.value = 99
    # composite still works but no longer updated
