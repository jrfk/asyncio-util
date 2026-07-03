"""Regression tests for move_on_when / run_and_cancelling / wait_any.

Covers:
- move_on_when with a trigger that completes immediately (previously
  leaked CancelledError out of __aenter__; the body never ran).
- move_on_when with a raising trigger (previously swallowed the
  exception and let the body run to completion).
- run_and_cancelling with a failed background task while the body is
  raising (previously masked the body's exception).
- wait_any/wait_all task leak when creating a task raises synchronously.
"""

import asyncio

import pytest

from asyncio_util import (
    move_on_when,
    run_and_cancelling,
    wait_all,
    wait_any,
)


class TestMoveOnWhenImmediateTrigger:
    async def test_already_set_event_does_not_leak_cancellation(self):
        event = asyncio.Event()
        event.set()
        ran_body = False

        async with move_on_when(event.wait) as scope:
            ran_body = True
            await asyncio.sleep(10)

        assert ran_body
        assert scope.cancelled_caught

    async def test_trigger_completing_without_awaiting(self):
        async def instant():
            return None

        async with move_on_when(instant) as scope:
            await asyncio.sleep(10)

        assert scope.cancelled_caught


class TestMoveOnWhenRaisingTrigger:
    async def test_trigger_exception_propagates_and_cancels_body(self):
        body_completed = False

        async def bad_trigger():
            await asyncio.sleep(0.01)
            raise ValueError("trigger boom")

        with pytest.raises(ValueError, match="trigger boom"):
            async with move_on_when(bad_trigger):
                await asyncio.sleep(10)
                body_completed = True

        assert not body_completed

    async def test_body_exception_wins_over_trigger_exception(self):
        async def bad_trigger():
            raise ValueError("trigger boom")

        with pytest.raises(RuntimeError, match="body boom"):
            async with move_on_when(bad_trigger):
                raise RuntimeError("body boom")


class TestRunAndCancellingExceptionMasking:
    async def test_body_exception_is_not_masked_by_background_failure(self):
        async def failing_background():
            raise ValueError("bg boom")

        with pytest.raises(RuntimeError, match="body boom"):
            async with run_and_cancelling(failing_background):
                await asyncio.sleep(0.05)  # let the background task fail
                raise RuntimeError("body boom")

    async def test_background_failure_propagates_when_body_is_clean(self):
        async def failing_background():
            raise ValueError("bg boom")

        with pytest.raises(ValueError, match="bg boom"):
            async with run_and_cancelling(failing_background):
                await asyncio.sleep(0.05)


def _pending_stray_tasks() -> list[asyncio.Task]:
    return [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]


class TestWaitHelpersTaskLeak:
    async def test_wait_any_cancels_started_tasks_on_sync_creation_error(self):
        async def waiter():
            await asyncio.sleep(10)

        def broken():
            raise RuntimeError("sync failure")

        with pytest.raises(RuntimeError, match="sync failure"):
            await wait_any(waiter, broken)
        # The already-created waiter task must not be left pending.
        await asyncio.sleep(0)
        assert _pending_stray_tasks() == []

    async def test_wait_all_cancels_started_tasks_on_sync_creation_error(self):
        async def waiter():
            await asyncio.sleep(10)

        def broken():
            raise RuntimeError("sync failure")

        with pytest.raises(RuntimeError, match="sync failure"):
            await wait_all(waiter, broken)
        await asyncio.sleep(0)
        assert _pending_stray_tasks() == []
