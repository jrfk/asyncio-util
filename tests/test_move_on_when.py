import asyncio

import pytest

from asyncio_util import CancelScope, move_on_when


@pytest.mark.asyncio
async def test_body_completes_before_trigger():
    """Body finishes naturally; trigger is cancelled."""
    result = []

    async def trigger():
        await asyncio.sleep(1.0)

    async with move_on_when(trigger) as scope:
        result.append("done")

    assert result == ["done"]
    assert scope.cancelled_caught is False


@pytest.mark.asyncio
async def test_trigger_cancels_body():
    """Trigger fires while body is sleeping."""

    async def trigger():
        await asyncio.sleep(0.05)

    async with move_on_when(trigger) as scope:
        await asyncio.sleep(10.0)  # Should be interrupted

    assert scope.cancelled_caught is True


@pytest.mark.asyncio
async def test_trigger_with_event():
    """Using an asyncio.Event as trigger."""
    event = asyncio.Event()

    async def set_event():
        await asyncio.sleep(0.05)
        event.set()

    asyncio.create_task(set_event())

    async with move_on_when(event.wait) as scope:
        await asyncio.sleep(10.0)

    assert scope.cancelled_caught is True


@pytest.mark.asyncio
async def test_scope_attributes():
    scope = CancelScope()
    assert scope.cancelled_caught is False
    assert scope._should_cancel is False


@pytest.mark.asyncio
async def test_body_exception_cleans_up_trigger():
    """If body raises, trigger task is still cleaned up."""
    trigger_cancelled = []

    async def trigger():
        try:
            await asyncio.sleep(10.0)
        except asyncio.CancelledError:
            trigger_cancelled.append(True)
            raise

    with pytest.raises(ValueError, match="body error"):
        async with move_on_when(trigger) as scope:
            raise ValueError("body error")

    await asyncio.sleep(0.01)
    assert trigger_cancelled == [True]
    assert scope.cancelled_caught is False


@pytest.mark.asyncio
async def test_external_cancellation_propagates():
    """External cancellation should not be swallowed."""
    async def trigger():
        await asyncio.sleep(10.0)

    async def run():
        async with move_on_when(trigger) as scope:
            await asyncio.sleep(10.0)

    task = asyncio.create_task(run())
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_empty_body():
    """Empty body exits immediately; trigger is cleaned up."""
    async def trigger():
        await asyncio.sleep(1.0)

    async with move_on_when(trigger) as scope:
        pass

    assert scope.cancelled_caught is False
