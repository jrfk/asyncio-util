import asyncio

import pytest

from asyncio_util import wait_any_map


@pytest.mark.asyncio
async def test_wait_any_map_basic():
    async def fast():
        await asyncio.sleep(0.05)
        return "fast_result"

    async def slow():
        await asyncio.sleep(10.0)
        return "slow_result"

    result = await wait_any_map(fast=fast, slow=slow)
    assert result.fast == "fast_result"
    assert result.slow is None


@pytest.mark.asyncio
async def test_wait_any_map_with_positional():
    async def bg():
        await asyncio.sleep(10.0)

    async def fast():
        await asyncio.sleep(0.05)
        return 42

    result = await wait_any_map(bg, value=fast)
    assert result.value == 42


@pytest.mark.asyncio
async def test_wait_any_map_no_args():
    result = await wait_any_map()
    assert result is None


@pytest.mark.asyncio
async def test_wait_any_map_propagates_exception():
    async def failing():
        raise ValueError("boom")

    async def slow():
        await asyncio.sleep(10.0)
        return "ok"

    with pytest.raises(ValueError, match="boom"):
        await wait_any_map(failing=failing, slow=slow)
