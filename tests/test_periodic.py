import asyncio

import pytest

from asyncio_util import periodic


@pytest.mark.asyncio
async def test_periodic_yields_elapsed_and_delta():
    results = []
    async for elapsed, delta in periodic(0.05):
        results.append((elapsed, delta))
        if len(results) == 3:
            break

    # First iteration: delta is None
    assert results[0][1] is None
    # First elapsed should be ~0
    assert results[0][0] < 0.02

    # Subsequent iterations: delta should be close to period
    for _, delta in results[1:]:
        assert delta is not None
        assert 0.03 < delta < 0.15

    # Elapsed should increase
    assert results[1][0] > results[0][0]
    assert results[2][0] > results[1][0]


@pytest.mark.asyncio
async def test_periodic_negative_period():
    with pytest.raises(ValueError, match="period must be positive"):
        async for _ in periodic(-1.0):
            break


@pytest.mark.asyncio
async def test_periodic_zero_period():
    with pytest.raises(ValueError, match="period must be positive"):
        async for _ in periodic(0.0):
            break


@pytest.mark.asyncio
async def test_periodic_overrun():
    """When body takes longer than period, next iteration starts immediately."""
    results = []
    async for elapsed, delta in periodic(0.01):
        results.append((elapsed, delta))
        if len(results) < 3:
            await asyncio.sleep(0.05)  # Overrun the period
        if len(results) == 4:
            break

    # After overrun, iteration should still happen (not hang)
    assert len(results) == 4
