from __future__ import annotations

from collections import namedtuple
from contextlib import ExitStack
from typing import Any, Callable, TypeVar

from asyncio_util._async_value import AsyncValue

T_OUT = TypeVar("T_OUT")


def compose_values(
    *,
    _transform_: Callable[..., T_OUT] | None = None,
    **value_map: AsyncValue[Any],
) -> _ComposeContext[T_OUT]:
    """Compose multiple AsyncValues into a single derived AsyncValue.

    Changes to any input AsyncValue automatically update the output.

    Usage::

        with compose_values(x=val_x, y=val_y) as composite:
            # composite.value is a namedtuple(x=..., y=...)
            await composite.wait_value(lambda v: v.x > 10)

        # With transform:
        with compose_values(_transform_=lambda v: v.x + v.y,
                            x=val_x, y=val_y) as total:
            await total.wait_value(lambda v: v > 100)

    Args:
        _transform_: Optional function to transform the composite
            namedtuple into the output value.
        **value_map: Named AsyncValue sources.

    Returns:
        A context manager yielding the composed AsyncValue.
    """
    return _ComposeContext(_transform_, value_map)


class _ComposeContext:
    def __init__(
        self,
        transform: Callable[..., Any] | None,
        value_map: dict[str, AsyncValue[Any]],
    ):
        self._transform = transform
        self._value_map = value_map

    def __enter__(self) -> AsyncValue[Any]:
        field_names = list(self._value_map.keys())
        composite_type = namedtuple("CompositeValue", field_names)  # type: ignore[misc]
        transform = self._transform

        current_values = {
            name: av.value for name, av in self._value_map.items()
        }
        composite = composite_type(**current_values)

        if transform is not None:
            output: AsyncValue[Any] = AsyncValue(transform(composite))
        else:
            output = AsyncValue(composite)

        self._stack = ExitStack()

        for name, src in self._value_map.items():

            def _make_updater(field: str) -> Callable[[Any], bool]:
                def _update(new_val: Any) -> bool:
                    nonlocal composite
                    composite = composite._replace(**{field: new_val})
                    if transform is not None:
                        output.value = transform(composite)
                    else:
                        output.value = composite
                    return False  # Never "matches" - just a side effect
                return _update

            updater = _make_updater(name)
            self._stack.enter_context(
                src._level_results.open_ref(updater)
            )

        self._output = output
        return output

    def __exit__(self, *exc_info: Any) -> None:
        self._stack.close()
