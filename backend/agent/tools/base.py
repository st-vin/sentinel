"""Base tool interface for all Sentinel MCP adapters."""
from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import Any


class BaseSentinelTool(ABC):
    name: str
    description: str

    @abstractmethod
    def _run(self, **kwargs: Any) -> dict:
        """Synchronous execution."""

    async def _arun(self, **kwargs: Any) -> dict:
        """Async execution — runs sync method in executor by default."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self._run(**kwargs))
