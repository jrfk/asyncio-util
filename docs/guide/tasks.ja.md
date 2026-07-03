# タスクとキャンセル

asyncio には `create_task`・`gather`・`wait` があります。強力ですが、タスクを
リークさせやすい道具でもあります。ここで紹介するヘルパーは、よくあるパターンを
*構造化*された形に包みます。ヘルパーが開始したタスクは、制御が戻る前に必ず
キャンセルされ、終了まで待たれます。

いずれも**引数なしの async callable**(コルーチンオブジェクトではなく)を
受け取ります。引数が必要なら `functools.partial` か `lambda` を使って
ください。

```python
from functools import partial

await wait_any(partial(fetch, url1), partial(fetch, url2))
```

## wait_any — 最初の 1 つが勝つ

[`wait_any()`][asyncio_util.wait_any] は callable を並行実行し、**最初**の
完了で戻ります。まだ走っているものはすべてキャンセルされ、終了を待たれます。

```python
from asyncio_util import wait_any

await wait_any(
    lambda: user_pressed_cancel.wait_value(True),
    lambda: job.wait_value("done"),
)
```

勝者が例外を投げていた場合、その例外が伝播します。

## wait_all — 全員が完了する

[`wait_all()`][asyncio_util.wait_all] は**すべて**の callable が完了したときに
戻ります。どれかが例外を投げると、残りはキャンセルされ、例外が伝播します。

```python
from asyncio_util import wait_all

await wait_all(sync_database, sync_cache, sync_search_index)
```

## wait_any_map — どれが、何を返して勝ったのか

[`wait_any_map()`][asyncio_util.wait_any_map] は、*どの*ブランチが完了し、
何を返したのかを知りたいときの `wait_any` です。キーワード引数でブランチに
名前を付けると、結果は namedtuple で返り、完了したブランチだけが
非 `None` になります。

```python
from asyncio_util import wait_any_map

result = await wait_any_map(
    timeout=lambda: asyncio.sleep(5),
    value=lambda: av.wait_value(lambda v: v > 10),
)
if result.value is not None:
    process(result.value)
else:
    print("タイムアウトしました")
```

## move_on_when — シグナルでブロックをキャンセル

[`move_on_when()`][asyncio_util.move_on_when] は、*トリガー*コルーチンが
完了するまでブロックを実行し、完了したらブロックをキャンセルします。
`asyncio.timeout()` がブロックを*時間*で区切るのに対し、`move_on_when` は
**イベント**で区切ります。

```python
from asyncio_util import move_on_when

async with move_on_when(shutdown_requested.wait_value, True) as scope:
    await serve_forever()

if scope.cancelled_caught:
    print("シャットダウン要求により中断されました")
```

- yield される [`CancelScope`][asyncio_util.CancelScope] の
  `cancelled_caught` で、本体が自力で完了したのかトリガーに中断されたのかを
  判別できます。
- トリガーは、本体が最初の `await` に到達した時点で走り始めます。
- トリガー自体が例外を投げた場合、本体はキャンセルされ、トリガーの例外が
  ブロックから再送出されます。

!!! warning "asyncio の制約"
    トリガーの発火と、外部からのタスクキャンセルが同じ瞬間に起きた場合、
    外部キャンセルがトリガー起因と区別できず、握りつぶされる可能性が
    あります。これは asyncio の単一種別キャンセルに固有の制約です
    (trio はランタイムレベルのキャンセルスコープで解決しています)。
    `move_on_when` の本体は小さく保ってください。

## run_and_cancelling — ブロックにスコープされたバックグラウンドタスク

[`run_and_cancelling()`][asyncio_util.run_and_cancelling] は、ブロックの
実行中だけバックグラウンドタスクを走らせます。`move_on_when` の逆です。

```python
from asyncio_util import run_and_cancelling

async with run_and_cancelling(heartbeat, interval=1.0):
    await do_migration()
# ここで heartbeat はキャンセルされ、終了を待たれる
```

本体の実行中にバックグラウンドタスクが失敗しても、本体は中断されません。
失敗はブロックを抜けるときに再送出されます(本体自身の例外があれば
そちらが優先されます)。

## start_and_cancelling — タスクの準備完了を待つ

[`start_and_cancelling()`][asyncio_util.start_and_cancelling] は、起動
フェーズが必要なバックグラウンドタスクのための `run_and_cancelling` です。
callable は `task_status` キーワードを受け取り、準備ができたら
`task_status.set()` を呼びます。本体はそれまで開始されません。

```python
from asyncio_util import start_and_cancelling

async def server(*, task_status):
    listener = await create_listener()
    task_status.set()          # 準備完了 — 本体が進んでよい
    await serve(listener)

async with start_and_cancelling(server):
    await run_client_tests()   # サーバーは確実に listen 中
```

準備完了のシグナル前にタスクが失敗した場合は、ブロックに入らず、その場で
例外が送出されます。

## 使い分け

| やりたいこと | 使うもの |
| --- | --- |
| 複数の操作を競争させる | `wait_any` / `wait_any_map` |
| 複数の操作を完走させる | `wait_all` |
| イベント発火で作業を止める | `move_on_when` |
| 一定時間で作業を止める | `asyncio.timeout()`(標準ライブラリ) |
| ブロックの間だけ補助タスクを生かす | `run_and_cancelling` |
| …さらに起動完了を待ってから | `start_and_cancelling` |
