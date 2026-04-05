import asyncio

import pytest

from asyncio_util import azip, azip_longest


async def async_range(n):
    for i in range(n):
        await asyncio.sleep(0)
        yield i


@pytest.mark.asyncio
async def test_azip_basic():
    results = []
    async for pair in azip(async_range(3), async_range(3)):
        results.append(pair)
    assert results == [(0, 0), (1, 1), (2, 2)]


@pytest.mark.asyncio
async def test_azip_shortest():
    results = []
    async for pair in azip(async_range(2), async_range(5)):
        results.append(pair)
    assert results == [(0, 0), (1, 1)]


@pytest.mark.asyncio
async def test_azip_empty():
    results = []
    async for _ in azip():
        results.append(True)
    assert results == []


@pytest.mark.asyncio
async def test_azip_longest_basic():
    results = []
    async for pair in azip_longest(async_range(3), async_range(3)):
        results.append(pair)
    assert results == [(0, 0), (1, 1), (2, 2)]


@pytest.mark.asyncio
async def test_azip_longest_fill():
    results = []
    async for pair in azip_longest(async_range(2), async_range(4), fillvalue=-1):
        results.append(pair)
    assert results == [(0, 0), (1, 1), (-1, 2), (-1, 3)]


@pytest.mark.asyncio
async def test_azip_longest_empty():
    results = []
    async for _ in azip_longest():
        results.append(True)
    assert results == []
