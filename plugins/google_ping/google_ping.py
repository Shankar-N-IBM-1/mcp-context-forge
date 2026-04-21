# -*- coding: utf-8 -*-
"""Background ping plugin for periodic HTTP health checks."""

# Standard
import asyncio
import logging
from typing import Any, Optional

# Third-Party
import httpx

# First-Party
from mcpgateway.plugins.framework import Plugin, PluginConfig


class GooglePingPlugin(Plugin):
    """Plugin that periodically sends an HTTP GET request in the background."""

    def __init__(self, config: PluginConfig) -> None:
        super().__init__(config)
        plugin_settings: dict[str, Any] = self.config.config or {}
        self._task: Optional[asyncio.Task[None]] = None
        self._shutdown = asyncio.Event()
        self._interval = int(plugin_settings.get("interval", 30))
        self._url = str(plugin_settings.get("url", "https://google.com"))
        self._logger = logging.getLogger(f"{__name__}.{self.name}")
        # Set logger to WARNING level to ensure messages are visible
        self._logger.setLevel(logging.WARNING)

    async def initialize(self) -> None:
        """Start the background ping loop."""
        self._shutdown.clear()
        self._task = asyncio.create_task(self._ping_loop())
        msg = f"🚀 GooglePingPlugin STARTED - interval={self._interval}s url={self._url}"
        self._logger.warning(msg)
        print(msg, flush=True)

    async def _ping_loop(self) -> None:
        """Run periodic pings until shutdown is requested."""
        while not self._shutdown.is_set():
            try:
                await asyncio.wait_for(self._shutdown.wait(), timeout=self._interval)
                break
            except asyncio.TimeoutError:
                await self._ping_url()
            except asyncio.CancelledError:
                self._logger.debug("Background ping loop cancelled")
                raise

    async def _ping_url(self) -> None:
        """Make HTTP GET request and log the response."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(self._url)
                msg = f"⏰ PING: {self._url} | Status: {response.status_code} | Length: {len(response.content)} bytes"
                self._logger.warning(msg)
                print(msg, flush=True)
                
                # Log response headers (first few)
                headers_preview = dict(list(response.headers.items())[:3])
                headers_msg = f"   Headers: {headers_preview}"
                self._logger.warning(headers_msg)
                print(headers_msg, flush=True)
        except httpx.TimeoutException:
            msg = f"❌ PING TIMEOUT: {self._url}"
            self._logger.warning(msg)
            print(msg, flush=True)
        except Exception as e:
            msg = f"❌ PING ERROR: {self._url} | Error: {type(e).__name__}: {str(e)}"
            self._logger.warning(msg)
            print(msg, flush=True)

    async def shutdown(self) -> None:
        """Stop the background ping loop gracefully."""
        msg = "🛑 GooglePingPlugin SHUTTING DOWN"
        self._logger.warning(msg)
        print(msg, flush=True)
        self._shutdown.set()

        if self._task is None:
            return

        if not self._task.done():
            try:
                await asyncio.wait_for(self._task, timeout=5.0)
            except asyncio.TimeoutError:
                self._logger.warning("Ping task did not stop in time; cancelling")
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass

        self._task = None

# Made with Bob
