import asyncio

import pytest

from asyncio_util import AsyncBool, AsyncValue, open_held_for, open_hysteresis


@pytest.mark.asyncio
async def test_open_held_for_becomes_true():
    src = AsyncValue(42)

    async with open_held_for(src, duration=0.1) as held:
        assert held.value is False
        await asyncio.sleep(0.15)
        assert held.value is True


@pytest.mark.asyncio
async def test_open_held_for_resets_on_change():
    src = AsyncValue(1)

    async with open_held_for(src, duration=0.1) as held:
        await asyncio.sleep(0.05)
        src.value = 2  # Reset the timer
        await asyncio.sleep(0.07)
        # Should still be False since value changed 0.07s ago (< 0.1s)
        assert held.value is False
        await asyncio.sleep(0.05)
        assert held.value is True


@pytest.mark.asyncio
async def test_open_hysteresis_rising():
    src = AsyncBool(False)

    async with open_hysteresis(src, rising_duration=0.1, falling_duration=0.0) as out:
        assert out.value is False
        src.value = True
        await asyncio.sleep(0.05)
        # Not yet risen (only 0.05s < 0.1s)
        assert out.value is False
        await asyncio.sleep(0.07)
        # Now risen (0.12s > 0.1s)
        assert out.value is True


@pytest.mark.asyncio
async def test_open_hysteresis_falling():
    src = AsyncBool(True)

    async with open_hysteresis(src, rising_duration=0.0, falling_duration=0.1) as out:
        assert out.value is True
        src.value = False
        await asyncio.sleep(0.05)
        assert out.value is True  # Not yet fallen
        await asyncio.sleep(0.07)
        assert out.value is False  # Now fallen


@pytest.mark.asyncio
async def test_open_hysteresis_bounce_rejected():
    src = AsyncBool(False)

    async with open_hysteresis(src, rising_duration=0.1) as out:
        src.value = True
        await asyncio.sleep(0.05)
        src.value = False  # Bounce back before duration
        await asyncio.sleep(0.07)
        assert out.value is False  # Should not have risen
