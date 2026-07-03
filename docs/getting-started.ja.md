# はじめに

## 動作要件

- Python 3.10 以降(CPython または PyPy)
- サードパーティ依存なし

## インストール

!!! warning
    PyPI にはまだ公開されていません。GitHub からインストールしてください。

```console
pip install git+https://github.com/jrfk/asyncio-util
```

[uv](https://docs.astral.sh/uv/) を使う場合:

```console
uv add git+https://github.com/jrfk/asyncio-util
```

## はじめての AsyncValue

[`AsyncValue`][asyncio_util.AsyncValue] は初期値をラップします。読み書きは
`value` プロパティを通して、ふつうの属性と同じように行います。

```python
from asyncio_util import AsyncValue

score = AsyncValue(0)
print(score.value)   # 0
score.value = 10
print(score.value)   # 10
```

ふつうの属性との違いは、他のタスクが **await できる**ことです。

```python
import asyncio
from asyncio_util import AsyncValue

score = AsyncValue(0)

async def announcer():
    value = await score.wait_value(lambda v: v >= 100)
    print(f"{value} に到達！")

async def game():
    for points in (30, 40, 50):
        await asyncio.sleep(0.1)
        score.value += points   # プロパティは累算代入にも対応

async def main():
    await asyncio.gather(announcer(), game())

asyncio.run(main())
```

出力:

```text
120 に到達！
```

ここにポーリングはありません。`announcer()` は `score.value += points` の代入で
述語が真になるまで眠っていて、条件を満たしたまさにその値を受け取ります。

## 値と述語

待機系の API はすべて、**ふつうの値**(`==` で比較)と**述語関数**の
どちらでも受け付けます。

```python
await score.wait_value(100)                  # value == 100
await score.wait_value(lambda v: v >= 100)   # predicate(value) が True
```

!!! tip "None を待つ"
    `None` も他の値と同じように扱われます。
    `await av.wait_value(None)` は値が `None` になるまで待ちます。

## タイムアウト

`wait_value()` と `wait_transition()` は `timeout` 引数を受け取り、期限切れで
`asyncio.TimeoutError` を送出します。

```python
try:
    await score.wait_value(100, timeout=1.0)
except asyncio.TimeoutError:
    print("タイムアウト！")
```

標準ライブラリのイディオムとの組み合わせも同様に機能します。コードベースの
流儀に合わせてください。

```python
await asyncio.wait_for(score.wait_value(100), timeout=1.0)   # 3.10+

async with asyncio.timeout(1.0):                             # 3.11+
    await score.wait_value(100)
```

タイムアウトなどで待機がキャンセルされた場合、内部のウェイターは即座に
片付けられます。リークはありません。

## 等値性について

現在の値と等しい(`==`)値の代入は**何もしません**。ウェイターは起きず、
遷移としても記録されません。この重複排除があるおかげで、派生値
([派生と合成](guide/deriving.md)を参照)を低コストに保てます。

## スレッド安全性

`AsyncValue` は**スレッドセーフではありません**。`value` への代入は
イベントループが動いているスレッドからのみ行ってください。別スレッドからは、
まずループに乗せます。

```python
loop.call_soon_threadsafe(setattr, av, "value", 42)
```

## 次のステップ

- [値を待つ](guide/waiting.md) — `wait_value`・`wait_transition`・`held_for` の
  詳細。
- [変化をイテレートする](guide/iterating.md) — 値をストリームとして消費する。
- [派生と合成](guide/deriving.md) — 値から値を組み立てる。
- [タスクとキャンセル](guide/tasks.md) — `AsyncValue` 以外の構造化ヘルパー。
- [イベント・ストリーム・タイミング](guide/streams.md) — 残りのツール群。
