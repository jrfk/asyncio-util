import asyncio

import pytest

from asyncio_util import AsyncBool


@pytest.mark.asyncio
async def test_default_value():
    b = AsyncBool()
    assert b.value is False


@pytest.mark.asyncio
async def test_initial_value():
    b = AsyncBool(True)
    assert b.value is True


@pytest.mark.asyncio
async def test_wait_value_true():
    b = AsyncBool()

    async def set_later():
        await asyncio.sleep(0.05)
        b.value = True

    asyncio.create_task(set_later())
    result = await b.wait_value(True)
    assert result is True


@pytest.mark.asyncio
async def test_wait_value_false():
    b = AsyncBool(True)

    async def set_later():
        await asyncio.sleep(0.05)
        b.value = False

    asyncio.create_task(set_later())
    result = await b.wait_value(False)
    assert result is False


@pytest.mark.asyncio
async def test_wait_transition():
    b = AsyncBool()

    async def toggle():
        await asyncio.sleep(0.05)
        b.value = True

    asyncio.create_task(toggle())
    new, old = await b.wait_transition()
    assert new is True
    assert old is False


@pytest.mark.asyncio
async def test_repr():
    b = AsyncBool()
    assert repr(b) == "AsyncBool(False)"
    b.value = True
    assert repr(b) == "AsyncBool(True)"
