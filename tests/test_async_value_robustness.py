"""Robustness tests: raising predicates must not corrupt delivery.

A predicate that raises is an application bug, but it must be delivered
to its own waiter — not crash the assigning task, and not prevent other
waiters from being notified for the same change.
"""

import asyncio

import pytest

from asyncio_util import AsyncValue


async def spin(count: int = 3) -> None:
    for _ in range(count):
        await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_predicate_exception_is_delivered_to_the_waiter():
    value = AsyncValue(0)

    def bad_predicate(v):
        if v == 1:
            raise RuntimeError("boom")
        return False

    task = asyncio.ensure_future(value.wait_value(bad_predicate))
    await spin()
    value.value = 1  # must not raise in the assigning task
    with pytest.raises(RuntimeError, match="boom"):
        await asyncio.wait_for(task, timeout=1)


@pytest.mark.asyncio
async def test_predicate_exception_does_not_starve_other_waiters():
    value = AsyncValue(0)

    def bad_predicate(v):
        raise RuntimeError("boom")

    bad_task = asyncio.ensure_future(value.wait_value(bad_predicate))
    good_task = asyncio.ensure_future(value.wait_value(1))
    edge_task = asyncio.ensure_future(value.wait_transition())
    await spin()
    value.value = 1
    with pytest.raises(RuntimeError, match="boom"):
        await asyncio.wait_for(bad_task, timeout=1)
    assert await asyncio.wait_for(good_task, timeout=1) == 1
    assert await asyncio.wait_for(edge_task, timeout=1) == (1, 0)


@pytest.mark.asyncio
async def test_transform_exception_reaches_setter_after_notifications():
    value = AsyncValue(0)

    def bad_transform(v):
        if v == 1:
            raise RuntimeError("boom")
        return v

    async with value.open_transform(bad_transform):
        waiter = asyncio.ensure_future(value.wait_value(1))
        await spin()
        with pytest.raises(RuntimeError, match="boom"):
            value.value = 1
        # The waiter was still notified despite the transform error.
        assert await asyncio.wait_for(waiter, timeout=1) == 1


@pytest.mark.asyncio
async def test_rapid_synchronous_changes_are_not_missed():
    # The matching value is captured at assignment time, even if the
    # value changes again before the waiter gets to run.
    value = AsyncValue(10)
    task = asyncio.ensure_future(value.wait_value(20))
    await spin()
    value.value = 20
    value.value = 10
    assert await asyncio.wait_for(task, timeout=1) == 20
    assert value.value == 10
