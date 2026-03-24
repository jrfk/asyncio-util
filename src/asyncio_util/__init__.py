# SPDX-FileCopyrightText: 2024-present Junya Fukuda <junya.fukuda.e@gmail.com>
#
# SPDX-License-Identifier: MIT

from asyncio_util._async_bool import AsyncBool
from asyncio_util._async_itertools import azip, azip_longest
from asyncio_util._async_value import AsyncValue
from asyncio_util._async_value_transforms import open_held_for, open_hysteresis
from asyncio_util._awaitables import wait_all, wait_any, wait_any_map
from asyncio_util._compose_values import compose_values
from asyncio_util._iterators import iter_fail_after, iter_move_on_after
from asyncio_util._move_on_when import (
    CancelScope,
    move_on_when,
    run_and_cancelling,
    start_and_cancelling,
)
from asyncio_util._multicast_queue import MulticastQueue
from asyncio_util._periodic import periodic
from asyncio_util._repeated_event import RepeatedEvent

# Legacy aliases (compatible with trio_util naming)
BoolEvent = AsyncBool
ValueEvent = AsyncValue

__all__ = [
    "AsyncBool",
    "AsyncValue",
    "BoolEvent",
    "CancelScope",
    "MulticastQueue",
    "RepeatedEvent",
    "ValueEvent",
    "azip",
    "azip_longest",
    "compose_values",
    "iter_fail_after",
    "iter_move_on_after",
    "move_on_when",
    "open_held_for",
    "open_hysteresis",
    "periodic",
    "run_and_cancelling",
    "start_and_cancelling",
    "wait_all",
    "wait_any",
    "wait_any_map",
]
