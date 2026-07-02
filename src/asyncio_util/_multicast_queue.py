from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Generic, TypeVar

T = TypeVar("T")

_CLOSED = object()  # end-of-stream sentinel (distinct from any user value)


class MulticastQueue(Generic[T]):
    """A broadcast queue that delivers each item to every active listener.

    Note:
        This is a **lossy** queue: if a listener's internal buffer is full,
        new messages for that listener are silently dropped.  Increase
        *queue_size* if you need larger buffers, or consume items faster.

    Usage::

        mq = MulticastQueue()

        async with mq.listen() as q:
            async for item in q:
                process(item)

        # In another task:
        await mq.broadcast("hello")
    """

    def __init__(self, queue_size: int = 10) -> None:
        self._queue_size = queue_size
        self._listeners: list[asyncio.Queue[Any]] = []

    async def broadcast(self, value: T) -> None:
        """Send *value* to all active listeners."""
        for q in self._listeners:
            try:
                q.put_nowait(value)
            except asyncio.QueueFull:
                pass

    @asynccontextmanager
    async def listen(self) -> AsyncIterator[_Listener[T]]:
        """Register a listener and yield an async iterable of broadcast values."""
        q: asyncio.Queue[Any] = asyncio.Queue(maxsize=self._queue_size)
        self._listeners.append(q)
        try:
            yield _Listener(q)
        finally:
            self._listeners.remove(q)
            # Signal end of iteration; ensure the sentinel is delivered
            # even if the queue is full by dropping an item to make room.
            while True:
                try:
                    q.put_nowait(_CLOSED)
                    break
                except asyncio.QueueFull:
                    try:
                        q.get_nowait()
                    except asyncio.QueueEmpty:
                        break


class _Listener(Generic[T]):
    """Async iterable wrapper around a listener queue."""

    def __init__(self, queue: asyncio.Queue[Any]) -> None:
        self._queue = queue
        self._closed = False

    def __aiter__(self) -> _Listener[T]:
        return self

    async def __anext__(self) -> T:
        if self._closed:
            raise StopAsyncIteration
        value = await self._queue.get()
        if value is _CLOSED:
            self._closed = True
            raise StopAsyncIteration
        return value

    async def get(self) -> T:
        """Get the next broadcast value."""
        return await self.__anext__()
