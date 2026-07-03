# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-07-03

### Added

- Bilingual (English / 日本語) documentation built with MkDocs Material +
  mkdocs-static-i18n + mkdocstrings, deployed to GitHub Pages:
  guides for waiting, iterating, deriving/composing, tasks/cancellation,
  and events/streams, plus a full API reference.
- Runnable examples under `examples/` (state machine, debouncing,
  composing values).
- `py.typed` marker so type checkers pick up the annotations.
- Docs build job in CI and a GitHub Pages deployment workflow.
- Regression test suites for `held_for`, raising predicates, task
  helpers, and stream helpers.

### Fixed

- `AsyncValue.wait_value(..., held_for=N)` raised `asyncio.TimeoutError`
  when the condition *successfully* held for the duration; it now
  returns the value.
- `AsyncValue.eventual_values(..., held_for=N)` had the hold logic
  inverted (yielded on flicker, raised `TimeoutError` on a stable hold).
- A raising predicate corrupted delivery: the exception surfaced in the
  assigning task and later waiters were never notified. Predicate
  exceptions are now delivered to their own waiter; transform/compose
  errors are re-raised only after all notifications went out.
- `compose_values()` silently swallowed exceptions raised by
  `_transform_`, freezing the composite output at its last good value.
- `move_on_when()` leaked `CancelledError` to the caller (and never ran
  the body) when the trigger completed without awaiting, e.g.
  `move_on_when(already_set_event.wait)`.
- `move_on_when()` swallowed exceptions raised by the trigger; they now
  cancel the body and propagate.
- `run_and_cancelling()` / `start_and_cancelling()` masked the body's
  exception when the background task had also failed.
- `wait_any()` / `wait_all()` / `wait_any_map()` leaked already-started
  tasks when creating a later task raised synchronously.
- `MulticastQueue` treated a broadcast `None` as end-of-stream,
  terminating listeners early; a private sentinel is used instead.
- `periodic()` drifted: scheduling is now anchored to the absolute
  `start + k * period` grid and re-syncs after an overrun.

### Changed

- Requires Python 3.10+ (was 3.8+); CI covers 3.10–3.14.
- Project metadata: description, keywords, classifiers, documentation
  URL pointing to GitHub Pages.

## [0.0.1] - 2024-05-15

### Added

- Initial port of trio-util APIs to asyncio, created for a
  [PyCon US 2024 talk](https://us.pycon.org/2024/schedule/presentation/142/):
  `AsyncValue`, `AsyncBool`, `compose_values`, `open_held_for`,
  `open_hysteresis`, `wait_any`/`wait_all`/`wait_any_map`,
  `move_on_when`/`CancelScope`, `run_and_cancelling`/
  `start_and_cancelling`, `MulticastQueue`, `RepeatedEvent`,
  `periodic`, `azip`/`azip_longest`,
  `iter_move_on_after`/`iter_fail_after`.

[0.1.0]: https://github.com/jrfk/asyncio-util/releases/tag/v0.1.0
[0.0.1]: https://github.com/jrfk/asyncio-util/commit/acf53ed
