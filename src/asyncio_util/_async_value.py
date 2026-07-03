from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, contextmanager
from typing import (
    AsyncContextManager,
    AsyncIterator,
    Callable,
    Generic,
    Iterator,
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
        self._futures: set[asyncio.Future[None]] = set()

    async def park(self):
        future = asyncio.get_running_loop().create_future()
        self._futures.add(future)
        try:
            await future
        finally:
            self._futures.discard(future)

    def unpark_all(self, error: BaseException | None = None):
        futures, self._futures = self._futures, set()
        for future in futures:
            if not future.done():
                if error is not None:
                    future.set_exception(error)
                else:
                    future.set_result(None)


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
        if not isinstance(other, _ValueWrapper):
            return NotImplemented
        return self.value == other.value

    def __call__(self, x, *args):  # noqa: ARG002
        return x == self.value


class AsyncValue(Generic[T]):
    """A mutable value whose changes can be awaited.

    ``AsyncValue`` wraps a value and lets any number of tasks wait for
    states ("the value is 20") or transitions ("the value just changed
    to 20") without polling and without managing events by hand.

    Matching is evaluated synchronously at assignment time, so
    :meth:`wait_value` and :meth:`wait_transition` never miss a match
    even if the value changes again immediately afterwards.

    Assigning a value equal to the current one is a no-op and wakes
    nobody.

    Predicates must be fast, side-effect free, and must not raise: they
    run synchronously inside the ``value`` setter.  Because any callable
    is treated as a predicate, a value that is itself callable cannot be
    waited on by equality — wrap it: ``lambda v: v == target``.  If a
    predicate does raise, the exception is delivered to that waiter
    (raised from its ``await``); other waiters are unaffected.

    Note:
        ``AsyncValue`` is not thread-safe.  Assign ``value`` only from
        the thread running the event loop; from other threads use
        ``loop.call_soon_threadsafe``.

    Example:
        ```python
        av = AsyncValue(0)

        async def watcher():
            value = await av.wait_value(20)   # suspends until 20
            print(value)

        # elsewhere, later:
        av.value = 20                          # wakes the watcher
        ```
    """

    def __init__(self, value: T):
        self._value = value
        self._level_results = _RefCountedDefaultDict(_Result)
        self._edge_results = _RefCountedDefaultDict(_Result)
        self._transforms = _RefCountedDefaultDict(lambda: AsyncValue(None))
        self._listeners: list[Callable[[T, T], None]] = []

    def __repr__(self):
        return f"{self.__class__.__name__}({self.value})"

    @property
    def value(self) -> T:
        """The current value.

        Assigning a new value synchronously notifies all matching
        waiters.  Assigning a value equal to the current one does
        nothing.
        """
        return self._value

    @value.setter
    def value(self, x: T):
        if self._value != x:
            old = self._value
            new = self._value = x
            # A raising predicate or transform must not prevent the
            # remaining waiters from being notified: predicate errors are
            # delivered to their own waiters, transform errors are
            # re-raised only after every notification went out.
            transform_error: Exception | None = None
            for f, result in self._level_results.items():
                try:
                    matched = f(new)
                except Exception as exc:
                    result.event.unpark_all(exc)
                    continue
                if matched:
                    result.value = new
                    result.event.unpark_all()
            for f, result in self._edge_results.items():
                try:
                    matched = f(new, old)
                except Exception as exc:
                    result.event.unpark_all(exc)
                    continue
                if matched:
                    result.value = (new, old)
                    result.event.unpark_all()
            for f, output in self._transforms.items():
                try:
                    output.value = f(new)
                except Exception as exc:
                    transform_error = transform_error or exc
            for listener in list(self._listeners):
                try:
                    listener(new, old)
                except Exception as exc:
                    transform_error = transform_error or exc
            if transform_error is not None:
                raise transform_error

    async def _wait_predicate(self, result_map, predicate):
        with result_map.open_ref(predicate) as result:
            await result.event.park()
            return result.value

    @contextmanager
    def _subscribe(self, listener: Callable[[T, T], None]) -> Iterator[None]:
        """Invoke ``listener(new_value, old_value)`` on every change.

        Listener exceptions are re-raised to the code assigning
        ``value`` after all other notifications went out.
        """
        self._listeners.append(listener)
        try:
            yield
        finally:
            self._listeners.remove(listener)

    @overload
    async def wait_value(self, value: T, *, held_for=0.0, timeout=None) -> T: ...
    @overload
    async def wait_value(self, predicate: P, *, held_for=0.0, timeout=None) -> T: ...
    async def wait_value(
        self,
        value_or_predicate: T | P,
        *,
        held_for: float = 0.0,
        timeout: float | None = None,
    ) -> T:
        """Wait until the value matches, and return the matched value.

        Returns immediately if the current value already matches.
        Otherwise the match is captured at assignment time, so a
        matching value is returned even if the value changes again
        before this coroutine resumes (the current value may differ by
        then).

        Args:
            value_or_predicate: A plain value to compare with ``==``, or
                a callable ``predicate(value) -> bool``.  Any callable
                is treated as a predicate.
            held_for: If greater than 0, only return once the match has
                held for at least that many seconds.  Each time the
                match is lost, the hold timer restarts.
            timeout: If not None, raise :class:`asyncio.TimeoutError`
                when no match occurred within *timeout* seconds.

        Returns:
            The value that satisfied the match.
        """
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
            except asyncio.TimeoutError:
                timeout_message = "Operation timed out"
                raise asyncio.TimeoutError(timeout_message) from None
            if held_for > 0:
                try:
                    await asyncio.wait_for(
                        self.wait_value(lambda v: not predicate(v)), held_for
                    )
                    # The match was lost before the hold elapsed; wait again.
                    continue
                except asyncio.TimeoutError:
                    # The match was held for the full duration.  Re-check in
                    # case the value changed while the timeout was being
                    # processed.
                    if not predicate(self._value):
                        continue
                    value = self._value
            return value

    @overload
    async def eventual_values(self, value: T, held_for=0.0) -> AsyncIterator[T]:
        yield self._value

    @overload
    async def eventual_values(
        self, predicate: P = _any_value, held_for=0.0
    ) -> AsyncIterator[T]:
        yield self._value

    async def eventual_values(
        self,
        value_or_predicate: T | P = _any_value,
        held_for: float = 0.0,
    ) -> AsyncIterator[T]:
        """Iterate over matching values, always converging to the latest.

        Yields the current value first if it matches, then each
        matching value as it is assigned.  A slow consumer may miss
        intermediate values, but is always caught up with the latest
        matching value — hence "eventual".  Consecutive duplicates are
        suppressed.

        Args:
            value_or_predicate: A plain value to compare with ``==``, or
                a callable ``predicate(value) -> bool``.  Omit it to
                match every value.
            held_for: If greater than 0, only yield a value once it has
                matched continuously for that many seconds.

        Example:
            ```python
            async for state in av.eventual_values():
                redraw(state)
            ```
        """
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
                    try:
                        await asyncio.wait_for(not_predicate.event.park(), held_for)
                        # The match was lost before the hold elapsed; start over.
                        continue
                    except asyncio.TimeoutError:
                        # The match was held for the full duration.
                        if not predicate(self._value):
                            continue
                        last_value = self._value
                yield last_value
                if self._value == last_value:
                    await not_last_value.event.park()

    @overload
    async def wait_transition(self, value: T) -> tuple[T, T]: ...
    @overload
    async def wait_transition(self, predicate: P2 = _any_transition) -> tuple[T, T]: ...
    async def wait_transition(
        self,
        value_or_predicate: T | P2 = _any_transition,
        *,
        timeout: float | None = None,
    ) -> tuple[T, T]:
        """Wait for the next matching change, and return ``(value, old_value)``.

        Unlike :meth:`wait_value`, the current value is never a match:
        this waits for an *edge*, an actual assignment that changes the
        value.

        Args:
            value_or_predicate: A plain value the *new* value must equal,
                or a callable ``predicate(value, old_value) -> bool``.
                Omit it to match any change.
            timeout: If not None, raise :class:`asyncio.TimeoutError`
                when no matching change occurred within *timeout*
                seconds.

        Returns:
            The ``(value, old_value)`` pair captured at assignment time.
        """
        try:
            return await asyncio.wait_for(
                self._wait_predicate(self._edge_results, _ValueWrapper(value_or_predicate)),
                timeout,
            )
        except asyncio.TimeoutError:
            raise asyncio.TimeoutError("Operation timed out") from None

    @overload
    async def transitions(self, value: T) -> AsyncIterator[tuple[T, T]]:
        yield (self._value, self._value)

    @overload
    async def transitions(
        self, predicate: P2 = _any_transition
    ) -> AsyncIterator[tuple[T, T]]:
        yield (self._value, self._value)

    async def transitions(
        self,
        value_or_predicate: T | P2 = _any_transition,
    ) -> AsyncIterator[tuple[T, T]]:
        """Iterate over matching changes as ``(value, old_value)`` pairs.

        Like :meth:`wait_transition` in a loop: only edges are reported,
        never the current value.

        Warning:
            Transitions are not queued.  A change that happens while the
            loop body is still processing the previous one is missed.
            If every edge matters, have the producer push into an
            ``asyncio.Queue`` (or a :class:`~asyncio_util.MulticastQueue`)
            instead.

        Args:
            value_or_predicate: A plain value the *new* value must equal,
                or a callable ``predicate(value, old_value) -> bool``.
                Omit it to match any change.
        """
        predicate = _ValueWrapper(value_or_predicate)
        with self._edge_results.open_ref(predicate) as result:
            while True:
                await result.event.park()
                yield result.value

    @asynccontextmanager
    async def open_transform(
        self, function: Callable[[T], T_OUT]
    ) -> AsyncContextManager[AsyncValue[T_OUT]]:
        """Derive a new :class:`AsyncValue` that tracks ``function(value)``.

        Within the ``async with`` block, the derived value is updated
        synchronously on every assignment to this value.  Updates that
        produce an equal output are deduplicated by the derived value's
        own setter.  Opening the same function object twice shares one
        derived value (reference-counted).

        Args:
            function: A pure, non-raising function applied to each value.
                It runs inside the source's setter; if it raises, the
                exception propagates to the code assigning ``value``
                (after all other waiters have been notified).

        Example:
            ```python
            av = AsyncValue(3)
            async with av.open_transform(lambda x: x * 10) as derived:
                assert derived.value == 30
            ```
        """
        with self._transforms.open_ref(function) as output:
            if output.value is None:
                output.value = function(self.value)
            yield output
