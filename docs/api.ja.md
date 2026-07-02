# API リファレンス

公開シンボルはすべてトップレベルの `asyncio_util` パッケージからインポート
できます。

```python
from asyncio_util import AsyncValue, compose_values, wait_any, ...
```

trio-util 互換のため、`BoolEvent` と `ValueEvent` が `AsyncBool` と
`AsyncValue` のエイリアスとして提供されています。

!!! note
    docstring(以下の各説明文)は英語です。各機能の日本語の解説は
    [ガイド](guide/waiting.md)を参照してください。

## await できる値

::: asyncio_util.AsyncValue

::: asyncio_util.AsyncBool

::: asyncio_util.compose_values

::: asyncio_util.open_held_for

::: asyncio_util.open_hysteresis

## タスクとキャンセル

::: asyncio_util.wait_any

::: asyncio_util.wait_all

::: asyncio_util.wait_any_map

::: asyncio_util.move_on_when

::: asyncio_util.CancelScope

::: asyncio_util.run_and_cancelling

::: asyncio_util.start_and_cancelling

## イベント・ストリーム・タイミング

::: asyncio_util.RepeatedEvent

::: asyncio_util.MulticastQueue

::: asyncio_util.periodic

::: asyncio_util.azip

::: asyncio_util.azip_longest

::: asyncio_util.iter_move_on_after

::: asyncio_util.iter_fail_after
