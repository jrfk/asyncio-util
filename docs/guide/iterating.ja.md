# 変化をイテレートする

一度だけ待つなら `await`、反応し続けるなら `async for`。`AsyncValue` は、
意図的にセマンティクスを変えた 2 つの非同期イテレータを提供します。

| | [`eventual_values()`][asyncio_util.AsyncValue.eventual_values] | [`transitions()`][asyncio_util.AsyncValue.transitions] |
| --- | --- | --- |
| セマンティクス | レベル — 「値は何か」 | エッジ — 「何が変わったか」 |
| 生成するもの | マッチした値 | マッチした `(new, old)` ペア |
| 現在の値 | (マッチすれば)最初に生成 | 決して生成しない |
| 消費が遅いとき | **最新**の値までスキップ | 途中の変化を**取りこぼす** |
| 典型的な用途 | 状態の描画、目標値への同期 | イベントのログ、エッジのカウント |

## eventual_values — 状態を追いかける

`eventual_values()` は、(マッチしていれば)現在の値をまず生成し、以後は
変化のたびにマッチした値を生成します。**最新**の状態だけが重要な場面 —
UI の描画、リコンシリエーションループ、ウォッチドッグ — に最適です。

```python
async for state in connection_state.eventual_values():
    redraw_status_icon(state)
```

述語や値を渡せば、マッチする状態だけが流れてきます。

```python
async for _ in connection_state.eventual_values("disconnected"):
    schedule_reconnect()
```

### 正確なセマンティクス

- 同じ値が 2 回連続で生成されることはありません。
- ループ本体の実行中に値が変化した場合、途中の値はスキップされることが
  ありますが、イテレータは**必ず最新のマッチする値に収束します**。古い状態を
  描画したまま止まってしまうことはありません。
- イテレータが(処理中ではなく)*待機中*にマッチする値が設定された場合、
  その値は捕捉され、直後に値がまた変わっても生成されます。これは
  `wait_value()` の「取りこぼさない保証」と一貫しています。

```python
av = AsyncValue(0)

# 消費側が忙しい間に av.value が 1, 2, 3, 4, 5 と変化…
# …次のイテレーションで生成されるのは 5。1〜4 のスキップは仕様です。
```

### ストリームのデバウンス: held_for

`wait_value()` と同じく、`eventual_values()` も `held_for` を受け取ります。
値は、指定した秒数だけ連続してマッチし続けたときにのみ生成されます。
保持期間内に述語を出入りするような値はスキップされます。

```python
# しきい値超えが 2 秒間続いた読み値だけを受け取る。
async for reading in sensor.eventual_values(lambda v: v > 100, held_for=2.0):
    trigger_alarm(reading)
```

## transitions — 変化を追いかける

`transitions()` はマッチした変化ごとに `(value, old_value)` を生成します。
結果の状態ではなく*イベント*そのものが重要なときに使います。

```python
async for new, old in av.transitions(lambda new, old: new < old):
    logger.warning("値が %s から %s に低下", old, new)
```

### 取りこぼされる遷移

`transitions()` がエッジを報告するのは**実際に待機している間だけ**です。
ループ本体が前の変化を処理している間に起きた変化は失われます。エッジは
キューイングされません。

```python
async for new, old in av.transitions():
    await slow_handler(new)   # この await の間の変化は失われる
```

!!! warning "すべてのエッジが必要ならキューを使う"
    これは「現在の状態」モデルに固有の性質です。`AsyncValue` が保持するのは
    1 つの値であって、履歴ではありません。*すべての*変化を処理する必要が
    あるなら、プロデューサ側で `asyncio.Queue` に積んでください。

    ```python
    queue: asyncio.Queue[int] = asyncio.Queue()

    def set_value(v: int) -> None:
        av.value = v
        queue.put_nowait(v)   # 明示的な履歴
    ```

## イテレーションの終了

どちらのイテレータも無限です。通常の非同期イテレーションと同じ方法で
終了してください。

- ループから `break` する
- 消費しているタスクをキャンセルする
- ループをタイムアウトスコープで包む

いずれの場合も後片付けは自動です。イテレータが中断・クローズ・キャンセル
された瞬間にウェイターは除去されます。

```python
async def watch(av: AsyncValue[str]) -> None:
    async for state in av.eventual_values():
        if state == "shutdown":
            break
        await apply(state)
```
