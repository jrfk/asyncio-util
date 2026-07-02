# asyncio-util

[![Test](https://github.com/jrfk/asyncio-util/actions/workflows/test.yml/badge.svg)](https://github.com/jrfk/asyncio-util/actions/workflows/test.yml)
[![Docs](https://github.com/jrfk/asyncio-util/actions/workflows/docs.yml/badge.svg)](https://jrfk.github.io/asyncio-util/ja/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://spdx.org/licenses/MIT.html)

**[trio-util](https://github.com/groove-x/trio-util) から asyncio へ移植した
ユーティリティ集 — await できる値、キャンセルスコープ、繰り返しイベント、
その他いろいろ。**

[ドキュメント](https://jrfk.github.io/asyncio-util/ja/) | [English README](README.md)

> [!TIP]
> このプロジェクトは、trio-util を asyncio に移植する PyCon US 2024 の
> [トーク](https://us.pycon.org/2024/schedule/presentation/142/)のサンプル
> コードとして始まり、独立したライブラリに成長しました。

-----

中心となるのは `AsyncValue` — 任意の数のタスクが状態や遷移を *await* できる
値です。ポーリングループも、`Event` の手動管理も、取りこぼしの心配も
いりません。

```python
import asyncio
from asyncio_util import AsyncValue

connection_state = AsyncValue("disconnected")

async def watcher():
    # 値が条件を満たすまで待つ…
    await connection_state.wait_value("connected")
    print("接続しました！")

    # …あるいは値の変化に逐次反応する。
    async for state in connection_state.eventual_values():
        print(f"現在の状態: {state}")

async def main():
    task = asyncio.ensure_future(watcher())
    await asyncio.sleep(0)
    connection_state.value = "connecting"
    connection_state.value = "connected"
    await asyncio.sleep(0.1)
    task.cancel()

asyncio.run(main())
```

マッチ判定は**代入時に同期的に**行われるため、値が直後に元へ戻っても
マッチする変化を取りこぼしません。

```python
av = AsyncValue(10)

# 別の場所で: av.value = 20; av.value = 10   (高速な往復)
value = await av.wait_value(20)   # それでも 20 が返る
```

## 機能

**await できる値**

- `AsyncValue` / `AsyncBool` — `wait_value()`・`wait_transition()`・
  `eventual_values()`・`transitions()`。述語、`timeout=`、`held_for=`
  デバウンスに対応
- `open_transform(f)` — `f(value)` を追跡する派生 `AsyncValue`
- `compose_values(x=..., y=...)` — 複数の値にまたがる条件を await
- `open_held_for()` / `open_hysteresis()` — バタつく信号のための時間ベース
  フィルタ

**タスクとキャンセル**

- `wait_any()` / `wait_all()` / `wait_any_map()` — 構造化されたレースと
  ジョイン(開始したタスクは戻る前に必ずキャンセル・待機される)
- `move_on_when(trigger)` — イベント発火でブロックをキャンセル
- `run_and_cancelling(fn)` / `start_and_cancelling(fn)` — ブロックに
  スコープされたバックグラウンドタスク

**イベント・ストリーム・タイミング**

- `RepeatedEvent` — 何度も発火でき、複数リスナーを持てるイベント
- `MulticastQueue` — 各アイテムを全リスナーへブロードキャスト
- `periodic(period)` — ドリフトしない周期イテレーション
- `azip()` / `azip_longest()` — 非同期イテレータの async `zip`
- `iter_move_on_after()` / `iter_fail_after()` — アイテム単位のタイムアウト

依存ゼロ、型付き(`py.typed`)、Python 3.10+(CPython & PyPy)。

## インストール

> [!WARNING]
> PyPI にはまだ公開されていません。

```console
pip install git+https://github.com/jrfk/asyncio-util
```

## ドキュメント

ガイド(日本語 / English)と API リファレンス:
**https://jrfk.github.io/asyncio-util/ja/**

実行できるサンプルは [`examples/`](examples/) にあります。

## 開発

```console
uv sync --group dev
uv run pytest              # テスト
uv run mkdocs serve        # ドキュメントのプレビュー (uv sync --group docs)
```

## 謝辞

API は GROOVE X の [trio-util](https://github.com/groove-x/trio-util) を
モデルに、asyncio のプリミティブの上にゼロから再実装したものです。

## ライセンス

`asyncio-util` は [MIT](https://spdx.org/licenses/MIT.html) ライセンスの下で
配布されています。
