import asyncio

import pytest

from asyncio_util import wait_all, wait_any


@pytest.mark.asyncio
async def test_wait_any_returns_on_first():
    order = []

    async def fast():
        await asyncio.sleep(0.05)
        order.append("fast")

    async def slow():
        await asyncio.sleep(1.0)
        order.append("slow")

    await wait_any(fast, slow)
    assert order == ["fast"]


@pytest.mark.asyncio
async def test_wait_any_no_args():
    await wait_any()


@pytest.mark.asyncio
async def test_wait_any_single():
    result = []

    async def task():
        result.append(1)

    await wait_any(task)
    assert result == [1]


@pytest.mark.asyncio
async def test_wait_any_propagates_exception():
    async def failing():
        raise ValueError("boom")

    async def slow():
        await asyncio.sleep(1.0)

    with pytest.raises(ValueError, match="boom"):
        await wait_any(failing, slow)


@pytest.mark.asyncio
async def test_wait_all_waits_for_all():
    order = []

    async def fast():
        await asyncio.sleep(0.05)
        order.append("fast")

    async def slow():
        await asyncio.sleep(0.1)
        order.append("slow")

    await wait_all(fast, slow)
    assert "fast" in order
    assert "slow" in order


@pytest.mark.asyncio
async def test_wait_all_no_args():
    await wait_all()


@pytest.mark.asyncio
async def test_wait_all_propagates_exception():
    async def failing():
        raise ValueError("boom")

    async def slow():
        await asyncio.sleep(1.0)

    with pytest.raises(ValueError, match="boom"):
        await wait_all(failing, slow)


@pytest.mark.asyncio
async def test_wait_all_cancels_on_error():
    cancelled = []

    async def failing():
        raise ValueError("boom")

    async def slow():
        try:
            await asyncio.sleep(10.0)
        except asyncio.CancelledError:
            cancelled.append(True)
            raise

    with pytest.raises(ValueError, match="boom"):
        await wait_all(failing, slow)

    # Give cancelled task time to process
    await asyncio.sleep(0.01)
    assert cancelled == [True]
