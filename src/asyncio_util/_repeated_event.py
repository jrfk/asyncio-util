from __future__ import annotations

from typing import AsyncIterator

from asyncio_util._async_value import AsyncValue


class RepeatedEvent:
    """An event that can be set multiple times, supporting multiple listeners.

    Each call to :meth:`set` increments an internal counter.  Listeners
    can either observe every firing (eventual consistency via
    :meth:`events`) or only the latest (drop-while-busy via
    :meth:`unqueued_events`).
    """

    def __init__(self) -> None:
        self._event: AsyncValue[int] = AsyncValue(0)

    def set(self) -> None:
        """Fire the event, waking all current waiters."""
        self._event.value = self._event.value + 1

    async def wait(self) -> None:
        """Wait until the event is fired at least once after this call."""
        token = self._event.value
        await self._event.wait_value(lambda v: v > token)

    async def unqueued_events(self) -> AsyncIterator[None]:
        """Yield on each firing, dropping events that arrive during processing.

        Events that occur while the consumer is processing the previous
        one are silently dropped.
        """
        async for _ in self._event.transitions():
            yield

    async def events(self, *, repeat_last: bool = False) -> AsyncIterator[None]:
        """Yield on each firing with eventual-consistency guarantee.

        The iterator is guaranteed to yield at least once for the most
        recent event, even if intermediate events were missed.

        Args:
            repeat_last: If True, yield immediately for the current
                state before waiting for new events.
        """
        token = -1 if repeat_last else self._event.value
        async for value in self._event.eventual_values(lambda v: v > token):
            token = value
            yield
