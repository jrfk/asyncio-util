from __future__ import annotations

import asyncio
from typing import Iterable


async def cancel_tasks(tasks: Iterable[asyncio.Task[object]]) -> None:
    """Cancel all tasks and wait for them to finish, suppressing exceptions."""
    task_list = list(tasks)
    for task in task_list:
        task.cancel()
    for task in task_list:
        try:
            await task
        except BaseException:
            pass
