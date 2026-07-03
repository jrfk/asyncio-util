# asyncio-util

**trio-util から asyncio へ移植したユーティリティ集 — await できる値、
キャンセルスコープ、繰り返しイベント、その他いろいろ。**

`asyncio-util` は、GROOVE X 製
[trio-util](https://github.com/groove-x/trio-util) の使い心地を素の asyncio に
持ち込みます。中心となるのは [`AsyncValue`][asyncio_util.AsyncValue] —
任意の数のタスクが状態や遷移を *await* できる値です。ポーリングループも、
`Event` の手動管理も、取りこぼしの心配もいりません。

!!! info "この プロジェクトについて"
    このプロジェクトは、trio-util を asyncio に移植する
    [PyCon US 2024 トーク](https://us.pycon.org/2024/schedule/presentation/142/)
    のサンプルコードとして始まり、独立したライブラリに成長しました。

```python
import asyncio
from asyncio_util import AsyncValue

connection_state = AsyncValue("disconnected")

async def watcher():
    await connection_state.wait_value("connected")
    print("接続しました！")

async def main():
    task = asyncio.ensure_future(watcher())
    await asyncio.sleep(0)
    connection_state.value = "connected"   # watcher が起きる
    await task

asyncio.run(main())
```

## なぜ AsyncValue なのか

タスク間の通知には「共有状態 + `asyncio.Event`」を使うのが定石ですが、
これは思いのほか間違えやすい組み合わせです。

- `Event` は値を運びません。状態は別に持ち、両者の同期を自分で保つ必要が
  あります。
- 「X が 3 を超えるまで待つ」には *チェック → 待機 → クリア* のループが必要で、
  ウェイクアップの取りこぼしを避けるには慎重に書かなければなりません。
- 待っているタスクが動き出す前に値が 2 回変化すると、途中の値は静かに失われ
  ます。`20` を待つタスクは、値が `20` だった瞬間を見逃します。

`AsyncValue` はこの 3 つをまとめて解決します。値と通知は 1 つのオブジェクトに
まとまり、待機は `await` 1 回で書け、マッチ判定は**代入時に同期的に**行われる
ため、値が直後に元へ戻ってもマッチする変化を取りこぼしません。

```python
av = AsyncValue(10)

# 別の場所で: av.value = 20; av.value = 10   (高速な往復)
value = await av.wait_value(20)   # それでも 20 が返る
```

## 機能一覧

### await できる値

| API | 役割 |
| --- | --- |
| [`AsyncValue`][asyncio_util.AsyncValue] | 状態と遷移を await できる値 |
| [`AsyncBool`][asyncio_util.AsyncBool] | デフォルト `False` の `AsyncValue[bool]` |
| [`wait_value()`][asyncio_util.AsyncValue.wait_value] | 値または述語にマッチするまで待つ |
| [`wait_transition()`][asyncio_util.AsyncValue.wait_transition] | 次のマッチする*変化*(エッジ)を待つ |
| [`eventual_values()`][asyncio_util.AsyncValue.eventual_values] | 常に最新値へ収束する値のイテレータ |
| [`transitions()`][asyncio_util.AsyncValue.transitions] | `(new, old)` の変化ペアのイテレータ |
| [`open_transform()`][asyncio_util.AsyncValue.open_transform] | `f(value)` を追跡する派生 `AsyncValue` |
| [`compose_values()`][asyncio_util.compose_values] | 複数の `AsyncValue` を合成し、横断的な条件を await |
| [`open_held_for()`][asyncio_util.open_held_for] | 値が安定したら True になる `AsyncBool` |
| [`open_hysteresis()`][asyncio_util.open_hysteresis] | ブール値のヒステリシスフィルタ |

### タスクとキャンセル

| API | 役割 |
| --- | --- |
| [`wait_any()`][asyncio_util.wait_any] | 並行実行して最初の完了で戻る |
| [`wait_all()`][asyncio_util.wait_all] | 並行実行して全完了で戻る |
| [`wait_any_map()`][asyncio_util.wait_any_map] | *どれが*完了したかと結果も返す `wait_any` |
| [`move_on_when()`][asyncio_util.move_on_when] | トリガー完了時にブロックをキャンセル |
| [`run_and_cancelling()`][asyncio_util.run_and_cancelling] | ブロックにスコープされたバックグラウンドタスク |
| [`start_and_cancelling()`][asyncio_util.start_and_cancelling] | 同上 + 準備完了シグナルを待つ |

### イベント・ストリーム・タイミング

| API | 役割 |
| --- | --- |
| [`RepeatedEvent`][asyncio_util.RepeatedEvent] | 何度も発火でき、複数リスナーを持てるイベント |
| [`MulticastQueue`][asyncio_util.MulticastQueue] | 各アイテムを全リスナーへブロードキャスト |
| [`periodic()`][asyncio_util.periodic] | ドリフトしない周期イテレーション |
| [`azip()` / `azip_longest()`][asyncio_util.azip] | 非同期イテレータの async `zip` |
| [`iter_move_on_after()` / `iter_fail_after()`][asyncio_util.iter_move_on_after] | 非同期イテレータのアイテム単位タイムアウト |

- **依存ゼロ** — 標準ライブラリのみで動作します。
- **型付き** — `py.typed` マーカーを同梱。`AsyncValue` はジェネリクス
  (`AsyncValue[int]`、`AsyncValue[State]` など)に対応します。
- **Python 3.10+**、CPython と PyPy をサポート。

## インストール

!!! warning
    PyPI にはまだ公開されていません。GitHub からインストールしてください。

```console
pip install git+https://github.com/jrfk/asyncio-util
```

## 次に読むページ

- [はじめに](getting-started.md) — インストールと最初の一歩。
- [値を待つ](guide/waiting.md) — `wait_value`・`wait_transition`・タイムアウト・
  `held_for`。
- [変化をイテレートする](guide/iterating.md) — `eventual_values` と `transitions`、
  その正確なセマンティクス。
- [派生と合成](guide/deriving.md) — `open_transform`・`compose_values`・
  `open_held_for`・`open_hysteresis`。
- [タスクとキャンセル](guide/tasks.md) — `wait_any`・`move_on_when` など。
- [イベント・ストリーム・タイミング](guide/streams.md) — `RepeatedEvent`・
  `MulticastQueue`・`periodic`・非同期イテレーションヘルパー。
- [API リファレンス](api.md) — すべての公開シンボルとソースコード。

## 謝辞

API は GROOVE X の [trio-util](https://github.com/groove-x/trio-util) を
モデルに、asyncio のプリミティブの上に再実装したものです。
