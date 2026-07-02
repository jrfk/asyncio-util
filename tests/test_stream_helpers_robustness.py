"""Regression tests for compose_values, MulticastQueue and periodic.

Covers:
- compose_values: a raising _transform_ was silently swallowed, leaving
  the composite output frozen at its last good value.
- MulticastQueue: broadcasting a legitimate None terminated listeners
  (None doubled as the end-of-stream sentinel).
- periodic: scheduling drifted because targets were computed relative
  to the previous wake-up instead of the absolute start time.
"""

import asyncio

import pytest

from asyncio_util import AsyncValue, MulticastQueue, compose_values, periodic


class TestComposeValuesTransformErrors:
    async def test_transform_error_propagates_to_setter(self):
        x = AsyncValue(1)
        y = AsyncValue(0)

        with compose_values(_transform_=lambda s: s.y // s.x, x=x, y=y) as out:
            assert out.value == 0
            with pytest.raises(ZeroDivisionError):
                x.value = 0

    async def test_output_recovers_after_transform_error(self):
        x = AsyncValue(1)
        y = AsyncValue(8)

        with compose_values(_transform_=lambda s: s.y // s.x, x=x, y=y) as out:
            with pytest.raises(ZeroDivisionError):
                x.value = 0
            x.value = 2
            assert out.value == 4

    async def test_other_waiters_still_notified_on_transform_error(self):
        x = AsyncValue(1)

        with compose_values(_transform_=lambda s: 1 // s.x, x=x):
            waiter = asyncio.ensure_future(x.wait_value(0))
            await asyncio.sleep(0)
            with pytest.raises(ZeroDivisionError):
                x.value = 0
            assert await asyncio.wait_for(waiter, timeout=1) == 0


class TestMulticastQueueNoneValues:
    async def test_broadcasting_none_does_not_end_the_stream(self):
        mq: MulticastQueue[str | None] = MulticastQueue()
        received = []

        async def subscriber():
            async with mq.listen() as items:
                async for item in items:
                    received.append(item)
                    if len(received) == 3:
                        break

        task = asyncio.ensure_future(subscriber())
        await asyncio.sleep(0)
        await mq.broadcast("a")
        await mq.broadcast(None)
        await mq.broadcast("b")
        await asyncio.wait_for(task, timeout=1)
        assert received == ["a", None, "b"]


class TestPeriodicGrid:
    async def test_schedule_does_not_drift_after_overrun(self):
        loop = asyncio.get_running_loop()
        period = 0.05
        start = loop.time()
        wakes = []

        async for _elapsed, _delta in periodic(period):
            wakes.append(loop.time() - start)
            if len(wakes) == 2:
                await asyncio.sleep(period * 1.5)  # overrun one slot
            if len(wakes) == 5:
                break

        # After the overrun, later iterations must snap back to the
        # k * period grid instead of shifting permanently.
        final_offset = wakes[-1] % period
        assert min(final_offset, period - final_offset) < period * 0.4
