"""Metrics Synchronization Module.

Handles synchronization of server and tool metrics to FAM.

Copyright 2025
SPDX-License-Identifier: Apache-2.0
"""

from collections import defaultdict
from datetime import datetime, timedelta, timezone
import logging
from typing import Any, Dict, List, Optional

from mcpgateway.db import Server, ServerMetric, Tool, ToolMetric, SessionLocal

from .fam import FAMAssetCatalogClient, FAMMetricsPayload

logger = logging.getLogger(__name__)


class MetricsSyncTask:
    """Task for synchronizing metrics to FAM.

    Handles:
    - Querying server and tool metrics from database
    - Organizing metrics by server and tool
    - Building metrics payload
    - Submitting metrics to FAM
    - Tracking sync state
    """

    def __init__(self, fam_client: FAMAssetCatalogClient, sync_interval: int = 300):
        """Initialize metrics sync task.

        Args:
            fam_client: FAM API client for metrics operations
            sync_interval: How often to sync metrics (in seconds). Also used as the time window for metrics collection.
        """
        self._fam_client = fam_client
        self._sync_interval = sync_interval
        self._last_sync: Optional[datetime] = None
        self._sync_counter = 0

    async def execute(self) -> None:
        """Execute metrics synchronization task.

        Checks if sync interval has elapsed, then queries and syncs metrics.
        """
        # Check if it's time to sync
        if not self._should_sync():
            return

        try:
            with SessionLocal() as db:
                servers = db.query(Server).all()
                tools = db.query(Tool).all()

                # Query metrics from time window (use sync_interval converted to minutes)
                time_window_minutes = self._sync_interval / 60
                time_window_start = datetime.now(timezone.utc) - timedelta(minutes=time_window_minutes)

                server_metrics_raw = db.query(ServerMetric).filter(ServerMetric.timestamp >= time_window_start).all()

                tool_metrics_raw = db.query(ToolMetric).filter(ToolMetric.timestamp >= time_window_start).all()

                await self._sync_metrics(servers, tools, server_metrics_raw, tool_metrics_raw)

        except Exception as e:
            logger.error(f"Error in metrics sync task: {e}", exc_info=True)

    def _should_sync(self) -> bool:
        """Check if it's time to sync metrics.

        Returns:
            True if sync interval has elapsed or this is first sync
        """
        if self._last_sync is None:
            return True

        now = datetime.now(timezone.utc)
        time_since_last_sync = (now - self._last_sync).total_seconds()
        return time_since_last_sync >= self._sync_interval

    async def _sync_metrics(self, servers: List[Any], tools: List[Any], server_metrics_raw: List[Any], tool_metrics_raw: List[Any]) -> None:
        """Sync metrics to FAM.

        Args:
            servers: List of Server ORM objects
            tools: List of Tool ORM objects
            server_metrics_raw: List of ServerMetric objects
            tool_metrics_raw: List of ToolMetric objects
        """
        # Organize server metrics by server ID
        server_metrics_map = defaultdict(list)
        for metric in server_metrics_raw:
            server_metrics_map[str(metric.server_id)].append(metric)

        # Build tool-to-server mapping
        tool_to_server = self._build_tool_server_mapping(servers)

        # Organize tool metrics by server and tool
        tool_metrics_by_server = defaultdict(lambda: defaultdict(list))
        for metric in tool_metrics_raw:
            tool_id = str(metric.tool_id)
            server_id = tool_to_server.get(tool_id)
            if server_id:
                tool_metrics_by_server[server_id][tool_id].append(metric)

        # Build metrics payload
        now = datetime.now(timezone.utc)
        metrics_payload = FAMMetricsPayload.build_payload(timestamp=now, server_metrics_map=dict(server_metrics_map), tool_metrics_by_server={k: dict(v) for k, v in tool_metrics_by_server.items()})

        # Submit to FAM
        if await self._fam_client.submit_metrics(metrics_payload):
            self._last_sync = now
            self._sync_counter += 1

            # Log statistics
            total_tools = sum(len(tools) for tools in tool_metrics_by_server.values())
            logger.info(f"Metrics sync #{self._sync_counter} completed - " f"Servers: {len(server_metrics_map)}, " f"Tools: {total_tools}, " f"Time window: {self._sync_interval}s")
        else:
            logger.error("Failed to submit metrics to FAM")

    def _build_tool_server_mapping(self, servers: List[Any]) -> Dict[str, str]:
        """Build mapping from tool ID to server ID.

        Args:
            servers: List of Server ORM objects

        Returns:
            Dict mapping tool_id to server_id
        """
        tool_to_server = {}
        for server in servers:
            if hasattr(server, "tools") and server.tools:
                for tool in server.tools:
                    tool_to_server[str(tool.id)] = str(server.id)
        return tool_to_server

    def get_stats(self) -> Dict[str, Any]:
        """Get synchronization statistics.

        Returns:
            Dict with sync statistics
        """
        return {"sync_count": self._sync_counter, "last_sync": self._last_sync.isoformat() if self._last_sync else None, "sync_interval": self._sync_interval}


# Made with Bob
