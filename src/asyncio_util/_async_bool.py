from __future__ import annotations

from asyncio_util._async_value import AsyncValue


class AsyncBool(AsyncValue[bool]):
    """Async boolean value with wait/transition capabilities.

    Convenience subclass of AsyncValue[bool] with False as default.
    """

    def __init__(self, value: bool = False):
        super().__init__(value)
