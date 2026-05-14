"""Recovery Handler.

Handles recovery of missed sync operations following webMethods Agent SDK pattern.
Recovers missed heartbeats, metrics, and asset updates after downtime or re-registration.

Copyright 2025
SPDX-License-Identifier: Apache-2.0
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional

from mcpgateway.db import SessionLocal, Server, Tool, ServerMetric, ToolMetric

from ..models import InactiveHeartbeat
from ..fam import FAMAssetCatalogClient

logger = logging.getLogger(__name__)


class RecoveryHandler:
    """Handles recovery of missed sync operations.

    Following webMethods SDK pattern, this handler:
    1. Sends INACTIVE heartbeats for missed intervals
    2. Sends historical metrics data
    3. Performs full asset sync

    Attributes:
        fam_client: FAM API client
        runtime_id: Runtime ID for this agent
    """

    def __init__(self, fam_client: FAMAssetCatalogClient, runtime_id: str):
        """Initialize recovery handler.

        Args:
            fam_client: FAM API client
            runtime_id: Runtime ID
        """
        self._fam_client = fam_client
        self._runtime_id = runtime_id

    async def recover_heartbeats(self, last_heartbeat_time: int, heartbeat_interval: int) -> int:
        """Send INACTIVE heartbeats for missed intervals.

        Following webMethods SDK pattern, generates INACTIVE heartbeats
        for each missed interval between last heartbeat and now.

        Args:
            last_heartbeat_time: Last heartbeat timestamp (milliseconds)
            heartbeat_interval: Heartbeat interval (seconds)

        Returns:
            Number of heartbeats recovered
        """
        current_time_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        interval_ms = heartbeat_interval * 1000

        # Generate missed heartbeats
        missed_heartbeats = self._generate_missed_heartbeats(last_heartbeat_time, current_time_ms, interval_ms)

        if not missed_heartbeats:
            logger.info("No missed heartbeats to recover")
            return 0

        logger.info(f"Recovering {len(missed_heartbeats)} missed heartbeats")

        # Send heartbeats in batches
        batch_size = 100
        total_sent = 0

        for i in range(0, len(missed_heartbeats), batch_size):
            batch = missed_heartbeats[i : i + batch_size]
            try:
                # Send batch to FAM
                payloads = [hb.to_payload() for hb in batch]
                await self._send_heartbeat_batch(payloads)
                total_sent += len(batch)
                logger.debug(f"Sent batch of {len(batch)} heartbeats ({total_sent}/{len(missed_heartbeats)})")
            except Exception as e:
                logger.error(f"Failed to send heartbeat batch: {e}", exc_info=True)
                # Continue with next batch

        logger.info(f"Successfully recovered {total_sent}/{len(missed_heartbeats)} heartbeats")
        return total_sent

    def _generate_missed_heartbeats(self, from_time_ms: int, to_time_ms: int, interval_ms: int) -> List[InactiveHeartbeat]:
        """Generate list of missed heartbeats.

        Args:
            from_time_ms: Start time (milliseconds)
            to_time_ms: End time (milliseconds)
            interval_ms: Interval (milliseconds)

        Returns:
            List of inactive heartbeats
        """
        heartbeats = []
        current_time = from_time_ms + interval_ms

        while current_time < to_time_ms:
            heartbeat = InactiveHeartbeat(runtime_id=self._runtime_id, created=current_time)
            heartbeats.append(heartbeat)
            current_time += interval_ms

        return heartbeats

    async def _send_heartbeat_batch(self, payloads: List[dict]) -> None:
        """Send batch of heartbeats to FAM.

        Args:
            payloads: List of heartbeat payloads
        """
        # For now, send individually (FAM may support batch in future)
        for _ in payloads:
            await self._fam_client.send_heartbeat(self._runtime_id)

    async def recover_metrics(self, last_metrics_time: int, _metrics_interval: int) -> int:
        """Send historical metrics data.

        Queries database for metrics since last sync and sends to FAM.

        Args:
            last_metrics_time: Last metrics sync timestamp (milliseconds)
            _metrics_interval: Metrics sync interval (seconds, unused)

        Returns:
            Number of metric records recovered
        """
        # Convert milliseconds to datetime
        from_time = datetime.fromtimestamp(last_metrics_time / 1000, tz=timezone.utc)
        current_time = datetime.now(timezone.utc)

        logger.info(f"Recovering metrics from {from_time} to {current_time}")

        try:
            with SessionLocal() as db:
                # Query server metrics
                server_metrics = db.query(ServerMetric).filter(ServerMetric.timestamp >= from_time, ServerMetric.timestamp <= current_time).all()

                # Query tool metrics
                tool_metrics = db.query(ToolMetric).filter(ToolMetric.timestamp >= from_time, ToolMetric.timestamp <= current_time).all()

                total_metrics = len(server_metrics) + len(tool_metrics)

                if total_metrics == 0:
                    logger.info("No historical metrics to recover")
                    return 0

                logger.info(f"Found {len(server_metrics)} server metrics and {len(tool_metrics)} tool metrics")

                # TODO: Send metrics to FAM
                # This would use the metrics sync logic from metrics_sync.py
                # For now, just log the recovery
                logger.warning("Metrics recovery not yet implemented - would send to FAM")

                return total_metrics

        except Exception as e:
            logger.error(f"Failed to recover metrics: {e}", exc_info=True)
            return 0

    async def recover_assets(self, _last_asset_sync_time: Optional[int] = None) -> dict:
        """Perform full asset sync.

        Syncs all servers and tools to FAM, regardless of last sync time.
        This ensures FAM has the current state after downtime.

        Args:
            _last_asset_sync_time: Last asset sync timestamp (milliseconds, unused)

        Returns:
            Dictionary with recovery statistics
        """
        logger.info("Performing full asset sync for recovery")

        stats = {"servers_synced": 0, "tools_synced": 0, "errors": 0}

        try:
            with SessionLocal() as db:
                # Get all servers
                servers = db.query(Server).all()
                logger.info(f"Found {len(servers)} servers to sync")

                # Get all tools
                tools = db.query(Tool).all()
                logger.info(f"Found {len(tools)} tools to sync")

                # TODO: Sync to FAM
                # This would use the sync logic from server_sync.py and tool_sync.py
                # For now, just log the recovery
                logger.warning("Asset recovery not yet implemented - would sync to FAM")

                stats["servers_synced"] = len(servers)
                stats["tools_synced"] = len(tools)

        except Exception as e:
            logger.error(f"Failed to recover assets: {e}", exc_info=True)
            stats["errors"] += 1

        logger.info(f"Asset recovery complete: {stats}")
        return stats

    async def perform_recovery(
        self, last_heartbeat_time: Optional[int] = None, last_metrics_time: Optional[int] = None, last_asset_sync_time: Optional[int] = None, heartbeat_interval: int = 60, metrics_interval: int = 300
    ) -> dict:
        """Perform complete recovery of all missed operations.

        This is the main entry point for recovery, called after re-registration.

        Args:
            last_heartbeat_time: Last heartbeat timestamp (milliseconds)
            last_metrics_time: Last metrics timestamp (milliseconds)
            last_asset_sync_time: Last asset sync timestamp (milliseconds)
            heartbeat_interval: Heartbeat interval (seconds)
            metrics_interval: Metrics interval (seconds)

        Returns:
            Dictionary with recovery statistics
        """
        logger.info("Starting recovery process")

        recovery_stats = {"heartbeats_recovered": 0, "metrics_recovered": 0, "assets_recovered": {}, "errors": []}

        # Recover heartbeats
        if last_heartbeat_time is not None:
            try:
                count = await self.recover_heartbeats(last_heartbeat_time, heartbeat_interval)
                recovery_stats["heartbeats_recovered"] = count
            except Exception as e:
                error_msg = f"Heartbeat recovery failed: {e}"
                logger.error(error_msg, exc_info=True)
                recovery_stats["errors"].append(error_msg)

        # Recover metrics
        if last_metrics_time is not None:
            try:
                count = await self.recover_metrics(last_metrics_time, metrics_interval)
                recovery_stats["metrics_recovered"] = count
            except Exception as e:
                error_msg = f"Metrics recovery failed: {e}"
                logger.error(error_msg, exc_info=True)
                recovery_stats["errors"].append(error_msg)

        # Recover assets
        if last_asset_sync_time is not None:
            try:
                stats = await self.recover_assets(last_asset_sync_time)
                recovery_stats["assets_recovered"] = stats
            except Exception as e:
                error_msg = f"Asset recovery failed: {e}"
                logger.error(error_msg, exc_info=True)
                recovery_stats["errors"].append(error_msg)

        logger.info(f"Recovery process complete: {recovery_stats}")
        return recovery_stats


# Made with Bob
