# イベント・ストリーム・タイミング

await できる値のほかにも、`asyncio-util` は繰り返しイベント、ブロードキャスト、
周期実行、複数の非同期ソースのイテレーションのための小さなツール群を
提供します。

## RepeatedEvent — 何度も発火するイベント

`asyncio.Event` はワンショットです。一度 set されると、誰かが `clear()` を
忘れずに呼ぶまですべての `wait()` が即座に返ります — 典型的なレースの温床
です。[`RepeatedEvent`][asyncio_util.RepeatedEvent] は「(また)何かが起きた」
パターンを直接モデル化します。

```python
from asyncio_util import RepeatedEvent

changed = RepeatedEvent()

# プロデューサ側:
changed.set()          # 発火。何度でも呼べる

# コンシューマ側 — この時点以降の次の発火を待つ:
await changed.wait()
```

イテレーションは 2 スタイルあり、[`eventual_values` と `transitions`](iterating.md)
の関係に対応します。

```python
# 「少なくとも 1 回発火した」ことを見逃さない(結果整合性):
async for _ in changed.events():
    await rebuild_index()

# 実際に待っている間だけ反応。処理中の発火は破棄される:
async for _ in changed.unqueued_events():
    await redraw()
```

`events(repeat_last=True)` は、開始時に現在の状態に対しても 1 回 yield
します。起動時に現状を処理したいコンシューマに便利です。

## MulticastQueue — 全リスナーへブロードキャスト

`asyncio.Queue` は各アイテムを *1 つ*のコンシューマに届けます。
[`MulticastQueue`][asyncio_util.MulticastQueue] は各アイテムを
**すべてのアクティブなリスナー**に届けます。

```python
from asyncio_util import MulticastQueue

mq: MulticastQueue[str] = MulticastQueue()

async def subscriber(name: str):
    async with mq.listen() as items:
        async for item in items:
            print(name, "が受信:", item)

# 別の場所で:
await mq.broadcast("hello")
```

- リスナーが受け取るのは、**購読している間**(`listen()` の中)に
  ブロードキャストされたアイテムだけです。
- リスナーが購読をやめると、イテレーションはきれいに終了します。

!!! warning "損失は仕様です"
    各リスナーは有限のバッファ(`queue_size`、デフォルト 10)を持ちます。
    リスナーが遅れてバッファが埋まると、*そのリスナー向けの*新しいアイテムは
    静かに破棄されます。最も遅いコンシューマに合わせてバッファを
    サイジングするか、より速く消費してください。

## periodic — ドリフトしない周期実行

ループ内で `period` 秒 sleep する方式はドリフトします。毎回、本体の実行時間が
スケジュールに加算されていくからです。[`periodic()`][asyncio_util.periodic]
は代わりに時計上の固定点を狙い、実際のタイミングも教えてくれます。

```python
from asyncio_util import periodic

async for elapsed, delta in periodic(1.0):
    print(f"開始から {elapsed:.1f} 秒、前回から {delta} 秒")
    await poll_sensors()
```

- `elapsed` — ループ開始からの秒数。`delta` — 前回のイテレーションからの
  秒数(初回は `None`)。
- 本体が period を超過した場合、次のイテレーションはほぼ即座に、次の空き
  グリッドスロットで始まります。取り逃したスロットは「積み残し」に
  なりません。

## azip / azip_longest — 非同期イテレータの zip

[`azip()`][asyncio_util.azip] は複数の非同期イテレータを**並行に**
(順番にではなく)進め、結果のタプルを yield します。

```python
from asyncio_util import azip, azip_longest

async for left, right in azip(sensor_a.eventual_values(),
                              sensor_b.eventual_values()):
    compare(left, right)
```

`azip` は最短のソースで停止します。
[`azip_longest()`][asyncio_util.azip_longest] はすべてのソースが尽きるまで
続行し、終了したソースには `fillvalue`(デフォルト `None`)を補います。

## iter_move_on_after / iter_fail_after — アイテム単位のタイムアウト

任意の非同期イテレータに対して、**アイテム間**の待ち時間を制限します。

```python
from asyncio_util import iter_move_on_after, iter_fail_after

# 1 秒以内にアイテムが来なければ静かにイテレーションを終える:
async for msg in iter_move_on_after(1.0, message_stream):
    handle(msg)

# あるいはストールをエラーにする:
async for msg in iter_fail_after(1.0, message_stream):   # asyncio.TimeoutError
    handle(msg)
```

タイムアウトは各 `__anext__` 呼び出しに適用されます。イテレーション全体
ではありません。

## 使い分け

| やりたいこと | 使うもの |
| --- | --- |
| タスク間で「(また)起きた」を通知する | `RepeatedEvent` |
| 1 つのストリームを複数コンシューマに配る | `MulticastQueue` |
| N 秒ごとにドリフトなしで実行する | `periodic` |
| 複数の非同期ソースを足並みを揃えて消費する | `azip` / `azip_longest` |
| ストールしたストリームを打ち切る(または失敗させる) | `iter_move_on_after` / `iter_fail_after` |
| イベントだけでなく*状態*を運ぶ | [`AsyncValue`](waiting.md) |
