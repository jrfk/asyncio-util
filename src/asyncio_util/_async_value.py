from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import (
    AsyncContextManager,
    AsyncIterator,
    Callable,
    Generic,
    TypeVar,
    overload,
)

from asyncio_util._ref_counted_default_dict import _RefCountedDefaultDict

T = TypeVar("T")
T_OUT = TypeVar("T_OUT")
P = Callable[[T], bool]
P2 = Callable[[T, T], bool]


class _WaitQueue:
    def __init__(self):
        self.tasks = set()

    async def park(self):
        task = asyncio.current_task()
        self.tasks.add(task)
        try:
            await asyncio.get_running_loop().create_future()
        except asyncio.CancelledError:
            pass
        finally:
            if task in self.tasks:
                self.tasks.remove(task)

    def unpark_all(self):
        for task in self.tasks:
            if not task.done():
                task.cancel()
        self.tasks.clear()


def _any_transition(value, old_value):  # noqa: ARG001
    return True


def _any_value(value):  # noqa: ARG001
    return True


class _Result:
    def __init__(self):
        self.event = _WaitQueue()
        self.value = None


class _ValueWrapper:
    def __new__(cls, value_or_predicate):
        return (
            value_or_predicate if callable(value_or_predicate) else super().__new__(cls)
        )

    def __init__(self, value):
        self.value = value

    def __hash__(self):
        try:
            return hash(self.value)
        except TypeError:
            return super().__hash__()

    def __eq__(self, other):
        return self.value == other.value

    def __call__(self, x, *args):  # noqa: ARG002
        return x == self.value


class AsyncValue(Generic[T]):
    def __init__(self, value: T):
        self._value = value
        self._level_results = _RefCountedDefaultDict(_Result)
        self._edge_results = _RefCountedDefaultDict(_Result)
        self._transforms = _RefCountedDefaultDict(lambda: AsyncValue(None))

    def __repr__(self):
        return f"{self.__class__.__name__}({self.value})"

    @property
    def value(self) -> T:
        return self._value

    @value.setter
    def value(self, x: T):
        if self._value != x:
            old = self._value
            new = self._value = x
            for f, result in self._level_results.items():
                if f(new):
                    result.value = new
                    result.event.unpark_all()
            for f, result in self._edge_results.items():
                if f(new, old):
                    result.value = (new, old)
                    result.event.unpark_all()
            for f, output in self._transforms.items():
                output.value = f(new)

    async def _wait_predicate(self, result_map, predicate):
        with result_map.open_ref(predicate) as result:
            await result.event.park()
        return result.value

    @overload
    async def wait_value(self, value: T, *, held_for=0.0, timeout=None) -> T: ...
    @overload
    async def wait_value(self, predicate: P, *, held_for=0.0, timeout=None) -> T: ...
    async def wait_value(self, value_or_predicate, *, held_for=0.0, timeout=None):
        predicate = _ValueWrapper(value_or_predicate)
        while True:
            try:
                if not predicate(self._value):
                    value = await asyncio.wait_for(
                        self._wait_predicate(self._level_results, predicate), timeout
                    )
                else:
                    value = self._value
                    await asyncio.sleep(0)
                if held_for > 0:
                    await asyncio.wait_for(
                        self.wait_value(lambda v: not predicate(v)), held_for
                    )
                    continue
                break
            except asyncio.TimeoutError:
                timeout_message = "Operation timed out"
                raise asyncio.TimeoutError(timeout_message) from None
        return value

    @overload
    async def eventual_values(self, value: T, held_for=0.0) -> AsyncIterator[T]:
        yield self._value

    @overload
    async def eventual_values(
        self, predicate: P = _any_value, held_for=0.0
    ) -> AsyncIterator[T]:
        yield self._value

    async def eventual_values(self, value_or_predicate=_any_value, held_for=0.0):
        predicate = _ValueWrapper(value_or_predicate)
        last_value = self._value
        with self._level_results.open_ref(
            predicate
        ) as result, self._level_results.open_ref(
            lambda v: v != last_value
        ) as not_last_value, self._level_results.open_ref(
            lambda v: not predicate(v)
        ) as not_predicate:
            while True:
                if predicate(self._value):
                    last_value = self._value
                else:
                    await result.event.park()
                    last_value = result.value
                if held_for > 0:
                    await asyncio.wait_for(not_predicate.event.park(), held_for)
                yield last_value
                if self._value == last_value:
                    await not_last_value.event.park()

    @overload
    async def wait_transition(self, value: T) -> tuple[T, T]: ...
    @overload
    async def wait_transition(self, predicate: P2 = _any_transition) -> tuple[T, T]: ...
    async def wait_transition(
        self, value_or_predicate=_any_transition, *, timeout=None
    ):
        return await asyncio.wait_for(
            self._wait_predicate(self._edge_results, _ValueWrapper(value_or_predicate)),
            timeout,
        )

    @overload
    async def transitions(self, value: T) -> AsyncIterator[tuple[T, T]]:
        yield (self._value, self._value)

    @overload
    async def transitions(
        self, predicate: P2 = _any_transition
    ) -> AsyncIterator[tuple[T, T]]:
        yield (self._value, self._value)

    async def transitions(self, value_or_predicate=_any_transition):
        predicate = _ValueWrapper(value_or_predicate)
        with self._edge_results.open_ref(predicate) as result:
            while True:
                await result.event.park()
                yield result.value

    @asynccontextmanager
    async def open_transform(
        self, function: Callable[[T], T_OUT]
    ) -> AsyncContextManager[AsyncValue[T_OUT]]:
        with self._transforms.open_ref(function) as output:
            if output.value is None:
                output.value = function(self.value)
            yield output
