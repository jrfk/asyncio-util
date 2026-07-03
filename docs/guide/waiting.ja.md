# 値を待つ

`AsyncValue` の待機には、信号処理から借りた 2 つの区別があります。

- **レベル(Level)** — 「値が X *である*」。条件がすでに成り立っていれば
  即座に完了します。これが
  [`wait_value()`][asyncio_util.AsyncValue.wait_value] です。
- **エッジ(Edge)** — 「値が X *になる*」。実際の変化だけがカウントされ、
  現在の値はマッチしません。これが
  [`wait_transition()`][asyncio_util.AsyncValue.wait_transition] です。

## wait_value — レベル待機

```python
av = AsyncValue("disconnected")

# 特定の値を待つ:
await av.wait_value("connected")

# 述語でも:
await av.wait_value(lambda state: state in ("connected", "degraded"))
```

`wait_value()` は**マッチした値**を返します。現在の値がすでにマッチしていれば、
中断せずに即座に返ります。

### 取りこぼさない保証

述語は **`value` セッターの中で同期的に**評価されます。マッチした値はその瞬間に
捕捉されてウェイターに届けられます。待っているタスクがスケジュールされる前に
値が再び変化しても、です。

```python
av = AsyncValue(10)

async def waiter():
    return await av.wait_value(20)

task = asyncio.ensure_future(waiter())
await asyncio.sleep(0)   # ウェイターの登録を待つ

av.value = 20   # ここでマッチが捕捉される
av.value = 10   # 直後に元へ戻す

assert await task == 20    # それでもウェイターは 20 を受け取る
assert av.value == 10      # 現在の値は既に先へ進んでいる
```

!!! warning "返り値は「今の値」とは限らない"
    この捕捉セマンティクスのため、`wait_value()` が返すのは*マッチした*値で
    あって、*今の*値とは限りません。現在の状態が必要なら、あらためて
    `av.value` を読んでください。

## wait_transition — エッジ待機

`wait_transition()` は現在の状態を完全に無視して、次のマッチする**変化**を
待ちます。返り値は `(value, old_value)` のペアです。

```python
av = AsyncValue("disconnected")

# あらゆる変化:
value, old = await av.wait_transition()

# 特定の値への変化:
value, old = await av.wait_transition("connected")

# (new, old) を見る述語 — 例: 立ち上がりエッジのみ:
value, old = await av.wait_transition(lambda new, old: new > old)
```

エッジ述語は遷移の両側を見られるので、「接続が*切れた*ときだけ発火する」の
ようなパターンも 1 行で書けます。

```python
await av.wait_transition(
    lambda new, old: new == "disconnected" and old == "connected"
)
```

!!! note "等しい値の代入は遷移ではない"
    `x == av.value` となる `av.value = x` は何もしません。ウェイターは起きず、
    遷移にもなりません。

## held_for — デバウンス

条件が*安定して*成立してから動きたいことがあります。センサーの読み値、
ヘルスチェック、接続状態など。`wait_value()` に `held_for` を渡すと、
マッチが連続して保持されることを要求できます。

```python
# 接続が 5 秒間連続で維持されて初めて先へ進む。
await av.wait_value("connected", held_for=5.0)
```

保持期間の途中で条件が崩れるとタイマーは振り出しに戻り、待機が続きます。
述語が少なくとも `held_for` 秒間成立し続けたときにのみ返ります。

## タイムアウト

`wait_value()` と `wait_transition()` はオプションの `timeout`(秒)を受け取り、
マッチする前に期限が切れると `asyncio.TimeoutError` を送出します。

```python
try:
    value = await av.wait_value(20, timeout=1.0)
except asyncio.TimeoutError:
    ...
```

標準ライブラリのタイムアウトイディオムも使えます。イテレータ系 API を
時間制限したいときはこちらを使ってください。

=== "asyncio.wait_for (3.10+)"

    ```python
    value = await asyncio.wait_for(av.wait_value(20), timeout=1.0)
    ```

=== "asyncio.timeout (3.11+)"

    ```python
    async with asyncio.timeout(1.0):
        value = await av.wait_value(20)
    ```

キャンセル(タイムアウト、`task.cancel()`、タスクグループの中断)は常に
安全です。内部のウェイターは `finally` ブロックで除去されるため、待機が
どんな形で終わってもリークしません。

## 複数のタスクから待つ

同じ `AsyncValue` を、同じ条件でも異なる条件でも、任意の数のタスクが同時に
待てます。各ウェイターは独立していて、1 回の代入が条件を満たすすべての
ウェイターを起こします。

```python
results = await asyncio.gather(
    av.wait_value(7),
    av.wait_value(lambda v: v > 5),
    av.wait_transition(),
)
```

## 述語のルール

- 述語は `value` セッターの中で同期的に実行されます。**速く**、
  **副作用なし**に保ってください。
- 述語が例外を投げた場合、その例外は**その述語のウェイター**に届き、
  `await` から送出されます。他のウェイターや代入したタスクには影響しません。
  とはいえ、例外は投げないでください。
- 述語の中で await はできません(コルーチンではなく、ふつうの関数です)。
- callable な引数はすべて述語として扱われます。値そのものが callable な場合は、
  明示的な等値述語で待ってください:
  `av.wait_value(lambda v: v == target_fn)`。
