import asyncio

import pytest

from asyncio_util import run_and_cancelling, start_and_cancelling


@pytest.mark.asyncio
async def test_run_and_cancelling_basic():
    bg_started = False
    bg_cancelled = False

    async def background():
        nonlocal bg_started, bg_cancelled
        bg_started = True
        try:
            await asyncio.sleep(10.0)
        except asyncio.CancelledError:
            bg_cancelled = True
            raise

    async with run_and_cancelling(background):
        await asyncio.sleep(0.05)
        assert bg_started is True

    await asyncio.sleep(0.01)
    assert bg_cancelled is True


@pytest.mark.asyncio
async def test_run_and_cancelling_body_exception():
    bg_cancelled = False

    async def background():
        nonlocal bg_cancelled
        try:
            await asyncio.sleep(10.0)
        except asyncio.CancelledError:
            bg_cancelled = True
            raise

    with pytest.raises(ValueError, match="boom"):
        async with run_and_cancelling(background):
            await asyncio.sleep(0.01)
            raise ValueError("boom")

    await asyncio.sleep(0.01)
    assert bg_cancelled is True


@pytest.mark.asyncio
async def test_start_and_cancelling_basic():
    server_running = False
    server_cancelled = False

    async def server(*, task_status):
        nonlocal server_running, server_cancelled
        server_running = True
        task_status.set()
        try:
            await asyncio.sleep(10.0)
        except asyncio.CancelledError:
            server_cancelled = True
            raise

    async with start_and_cancelling(server):
        assert server_running is True

    await asyncio.sleep(0.01)
    assert server_cancelled is True


@pytest.mark.asyncio
async def test_start_and_cancelling_failure_before_start():
    async def failing_server(*, task_status):
        raise ValueError("startup failed")

    with pytest.raises(ValueError, match="startup failed"):
        async with start_and_cancelling(failing_server):
            pass
