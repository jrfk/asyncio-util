from __future__ import annotations

import asyncio
from typing import AsyncIterator, Generic, TypeVar

T = TypeVar("T")


class _IterWithTimeout(Generic[T]):
    """Base async iterator wrapper with per-item timeout."""

    __slots__ = ("_ait", "_timeout", "_stop_on_timeout")

    def __init__(
        self, timeout: float, ait: AsyncIterator[T], *, stop_on_timeout: bool
    ) -> None:
        self._ait = ait
        self._timeout = timeout
        self._stop_on_timeout = stop_on_timeout

    def __aiter__(self) -> _IterWithTimeout[T]:
        return self

    async def __anext__(self) -> T:
        try:
            return await asyncio.wait_for(self._ait.__anext__(), self._timeout)
        except asyncio.TimeoutError:
            if self._stop_on_timeout:
                raise StopAsyncIteration from None
            raise


class iter_move_on_after(_IterWithTimeout[T]):
    """Wrap an async iterator with a per-item timeout.

    If fetching the next item takes longer than *timeout* seconds,
    iteration stops silently.

    Usage::

        async for item in iter_move_on_after(1.0, some_aiter):
            process(item)
    """

    def __init__(self, timeout: float, ait: AsyncIterator[T]) -> None:
        super().__init__(timeout, ait, stop_on_timeout=True)


class iter_fail_after(_IterWithTimeout[T]):
    """Wrap an async iterator with a per-item timeout.

    If fetching the next item takes longer than *timeout* seconds,
    raises :class:`asyncio.TimeoutError`.

    Usage::

        async for item in iter_fail_after(1.0, some_aiter):
            process(item)
    """

    def __init__(self, timeout: float, ait: AsyncIterator[T]) -> None:
        super().__init__(timeout, ait, stop_on_timeout=False)
