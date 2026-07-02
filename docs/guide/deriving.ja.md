# 派生と合成

現実のシステムが見張るのは、生の値 1 つではありません。値の*関数*
(「華氏温度が 100 を超えたか？」)や、値の*組み合わせ*(「ロボットはドックに
いて、**かつ**充電済みか？」)です。`asyncio-util` はその両方に加えて、
バタつく信号のための時間ベースのフィルタを 2 つ提供します。

## open_transform — 値から値を派生させる

[`open_transform()`][asyncio_util.AsyncValue.open_transform] は、常に
`f(source.value)` と等しい新しい `AsyncValue` を返します。

```python
celsius = AsyncValue(25.0)

async with celsius.open_transform(lambda c: c * 9 / 5 + 32) as fahrenheit:
    assert fahrenheit.value == 77.0

    # 派生値は完全な AsyncValue — await もイテレートもできる:
    await fahrenheit.wait_value(lambda f: f > 100)
```

重要な性質:

- 更新は**同期的**です。`celsius.value = x` が返った時点で
  `fahrenheit.value` はすでに `f(x)` になっています。2 つの値が食い違う
  瞬間はありません。
- 更新は派生値自身のセッターを通るため、**重複排除**されます。`f` が
  2 つの入力を同じ出力に写すなら、派生値に遷移は発生しません。

    ```python
    parity = AsyncValue(1)
    async with parity.open_transform(lambda x: x % 2) as is_odd:
        parity.value = 3   # 1 -> 3。しかし 3 % 2 == 1 なので is_odd は変化しない
    ```

- **同じ関数オブジェクト**での `open_transform` は 1 つの派生値を共有します
  (内部で参照カウント管理)。
- `async with` ブロックを抜けると派生値は切り離されます。最後の値は保持
  しますが、追跡元にはもう追随しません。

!!! note "変換関数について"
    述語と同じく、変換関数は追跡元のセッターの中で実行されます。速く、純粋に、
    例外を投げないように保ってください。もし例外を投げた場合、他のすべての
    ウェイターへの通知が済んだ後で、`value` を代入したコードに伝播します。

## compose_values — 複数の値を合成する

[`compose_values()`][asyncio_util.compose_values] は、任意の数の
`AsyncValue` を 1 つにまとめます。合成後の値は**名前付きタプル**で、
どの入力が変化しても更新されます。

```python
from asyncio_util import AsyncValue, compose_values

docked = AsyncValue(False)
battery_percent = AsyncValue(15)

with compose_values(docked=docked, battery=battery_percent) as status:
    # status.value は namedtuple: (docked=False, battery=15)
    print(status.value.docked, status.value.battery)

    # 両方にまたがる条件を await する:
    await status.wait_value(lambda s: s.docked and s.battery >= 90)
```

これが「A **かつ** B になるまで待つ」への明快な答えです。イベントの手動
振り付けも、再チェックのループも不要 — 1 つの合成値に対する 1 つの述語だけです。

`_transform_` を渡すと、合成タプルを一段で別の値へ写像できます。

```python
with compose_values(_transform_=lambda s: s.x + s.y, x=x, y=y) as total:
    await total.wait_value(lambda t: t > 100)
```

合成値は `AsyncValue` *そのもの*なので、前の章までの内容がすべて適用できます。

```python
# どちらかの入力が変わるたびに反応する:
async for snapshot in status.eventual_values():
    update_dashboard(snapshot)

# 組み合わせに対するエッジ検出:
await status.wait_transition(
    lambda new, old: new.docked and not old.docked
)
```

## AsyncBool — ブール値のショートハンド

[`AsyncBool`][asyncio_util.AsyncBool] は、デフォルトが `False` の
`AsyncValue[bool]` です。フラグに便利です。

```python
from asyncio_util import AsyncBool

ready = AsyncBool()          # False で開始
await ready.wait_value(True)
```

(trio-util 互換のため、`BoolEvent` と `ValueEvent` が `AsyncBool` と
`AsyncValue` のエイリアスとして提供されています。)

## open_held_for — 「安定したか？」

[`open_held_for()`][asyncio_util.open_held_for] は*任意の* `AsyncValue` を
監視し、ソースが `duration` 秒間変化していない間 True になる `AsyncBool` を
返します。

```python
from asyncio_util import AsyncValue, open_held_for

position = AsyncValue((0.0, 0.0))

async with open_held_for(position, duration=2.0) as settled:
    await settled.wait_value(True)
    print("位置が 2 秒間安定しました")
```

ソースが変化するたびに出力は False に戻り、タイマーは振り出しに戻ります。

## open_hysteresis — ブール値のバタつき除去

[`open_hysteresis()`][asyncio_util.open_hysteresis] はブールの `AsyncValue` を
フィルタし、短いブリップが伝播しないようにします。出力は、入力が
`rising_duration` 秒間 True であり続けたときにのみ立ち上がり、
`falling_duration` 秒間 False であり続けたときにのみ立ち下がります。

```python
from asyncio_util import AsyncBool, open_hysteresis

link_up = AsyncBool()

async with open_hysteresis(link_up, rising_duration=1.0,
                           falling_duration=5.0) as stable_link:
    async for is_up, _ in stable_link.transitions():
        print("リンク", "回復" if is_up else "喪失")
```

200 ms のネットワークブリップは `stable_link` には届きません。

!!! note "バックグラウンドタスク"
    `open_held_for` と `open_hysteresis` は、`async with` ブロックが開いて
    いる間だけ小さなバックグラウンドタスクを走らせます。ブロックを抜けると
    キャンセルされ、終了を待ってから戻ります。

## 使い分け

| やりたいこと | 使うもの |
| --- | --- |
| 1 つのソースの `f(value)` を見張る | `open_transform` |
| 複数のソースにまたがる条件を await する | `compose_values` |
| 両方 — 例: `f(a, b)` | `compose_values` + `_transform_` |
| 値が落ち着いたことを知る | `open_held_for` |
| フラグの短いブリップを抑制する | `open_hysteresis` |
