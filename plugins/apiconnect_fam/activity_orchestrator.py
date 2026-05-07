"""Activity Orchestrator for Server Monitor Plugin.

Manages all activities following webMethods Agent SDK patterns.
Coordinates activity execution, statistics tracking, and health monitoring.

Copyright 2025
SPDX-License-Identifier: Apache-2.0
"""

# Standard
import asyncio
import logging
from typing import Any, Dict, List, Optional

# Local
from .activities.base import AbstractScheduledActivity
from .activities.check_fam_health import CheckFAMHealthActivity
from .activities.check_runtime_health import CheckRuntimeHealthActivity
from .activities.send_heartbeat import SendHeartbeatActivity
from .activities.send_metrics import SendMetricsActivity
from .activities.sync_servers import SyncServersActivity
from .activities.sync_tools import SyncToolsActivity
from .fam_client import FAMAssetCatalogClient
from .handlers.recovery_handler import RecoveryHandler
from .models import ActivityContext, SyncStatistics

logger = logging.getLogger(__name__)


class ActivityOrchestrator:
    """Orchestrates all activities for the Server Monitor Plugin.

    Manages activity lifecycle, execution scheduling, statistics tracking,
    and health monitoring following webMethods Agent SDK patterns.

    Attributes:
        context: Shared context for all activities
        fam_client: FAM API client
        recovery_handler: Recovery handler for missed operations
        activities: List of all managed activities
        _running: Whether orchestrator is running
        _task: Background task for activity execution
    """

    def __init__(
        self,
        fam_client: FAMAssetCatalogClient,
        runtime_id: str,
        fam_base_url: str,
        config: Dict[str, Any],
        heartbeat_interval: int = 60,
        metrics_interval: int = 300,
        server_sync_interval: int = 60,
        tool_sync_interval: int = 60,
        fam_health_check_interval: int = 30,
        runtime_health_check_interval: int = 60,
    ):
        """Initialize the activity orchestrator.

        Args:
            fam_client: FAM API client
            runtime_id: Runtime ID for this agent
            fam_base_url: Base URL for FAM API
            config: Plugin configuration dictionary
            heartbeat_interval: Heartbeat interval in seconds (default: 60, mandatory)
            metrics_interval: Metrics sync interval in seconds (default: 300, 0 to disable)
            server_sync_interval: Server sync interval in seconds (default: 60, 0 to disable)
            tool_sync_interval: Tool sync interval in seconds (default: 60, 0 to disable)
            fam_health_check_interval: FAM health check interval in seconds (default: 30)
            runtime_health_check_interval: Runtime health check interval in seconds (default: 60)
        """
        # Create shared context
        self.context = ActivityContext(runtime_id=runtime_id, fam_base_url=fam_base_url, config=config)

        self.fam_client = fam_client
        self.runtime_id = runtime_id

        # Initialize handlers
        self.recovery_handler = RecoveryHandler(fam_client=fam_client, runtime_id=runtime_id)

        # Initialize activities
        # Note: Order matters! Servers must sync before tools
        self.activities: List[AbstractScheduledActivity] = []

        # Create health check activities (independent, run first for monitoring)
        self.fam_health_activity = CheckFAMHealthActivity(context=self.context, fam_client=fam_client, check_interval=fam_health_check_interval)
        self.activities.append(self.fam_health_activity)

        self.runtime_health_activity = CheckRuntimeHealthActivity(context=self.context, check_interval=runtime_health_check_interval)
        self.activities.append(self.runtime_health_activity)

        # Create heartbeat activity (mandatory)
        self.heartbeat_activity = SendHeartbeatActivity(context=self.context, fam_client=fam_client, heartbeat_interval=heartbeat_interval)
        self.activities.append(self.heartbeat_activity)

        # Create metrics activity (optional, only if interval > 0)
        self.metrics_activity: Optional[SendMetricsActivity] = None
        if metrics_interval > 0:
            self.metrics_activity = SendMetricsActivity(context=self.context, fam_client=fam_client, metrics_interval=metrics_interval)
            self.activities.append(self.metrics_activity)
            logger.info(f"Metrics sync enabled with interval={metrics_interval}s")
        else:
            logger.info("Metrics sync disabled")

        # Create server sync activity (optional, only if interval > 0, must run before tools)
        self.server_sync_activity: Optional[SyncServersActivity] = None
        if server_sync_interval > 0:
            self.server_sync_activity = SyncServersActivity(context=self.context, fam_client=fam_client, sync_interval=server_sync_interval, orchestrator=self)
            self.activities.append(self.server_sync_activity)
            logger.info(f"Server asset sync enabled with interval={server_sync_interval}s")
        else:
            logger.info("Server asset sync disabled")

        # Create tool sync activity (optional, only if interval > 0, depends on servers)
        self.tool_sync_activity: Optional[SyncToolsActivity] = None
        if tool_sync_interval > 0:
            self.tool_sync_activity = SyncToolsActivity(context=self.context, fam_client=fam_client, sync_interval=tool_sync_interval, orchestrator=self)
            self.activities.append(self.tool_sync_activity)
            logger.info(f"Tool asset sync enabled with interval={tool_sync_interval}s")
        else:
            logger.info("Tool asset sync disabled")

        # Track if servers have been synced (for tool sync dependency)
        self._servers_synced_this_cycle = False

        # Orchestrator state
        self._running = False
        self._task: Optional[asyncio.Task] = None

        # Shared state for activity coordination
        # Maps ContextForge server ID -> FAM server ID
        self._server_id_mapping: Dict[str, str] = {}

        logger.info(
            f"ActivityOrchestrator initialized with {len(self.activities)} activities: "
            f"fam_health={fam_health_check_interval}s, runtime_health={runtime_health_check_interval}s, "
            f"heartbeat={heartbeat_interval}s, metrics={metrics_interval if metrics_interval > 0 else 'disabled'}s, "
            f"servers={server_sync_interval if server_sync_interval > 0 else 'disabled'}s, "
            f"tools={tool_sync_interval if tool_sync_interval > 0 else 'disabled'}s"
        )

    def get_server_id_mapping(self) -> Dict[str, str]:
        """Get the mapping of ContextForge server IDs to FAM server IDs.

        This is used by tool sync to get the mcpServerId for each tool.

        Returns:
            Dictionary mapping ContextForge server ID to FAM server ID
        """
        return self._server_id_mapping.copy()

    def update_server_id_mapping(self, contextforge_id: str, fam_id: str) -> None:
        """Update the server ID mapping.

        Called by server sync activity when a server is synced to FAM.

        Args:
            contextforge_id: ContextForge server ID
            fam_id: FAM server ID
        """
        self._server_id_mapping[contextforge_id] = fam_id
        logger.debug(f"Updated server ID mapping: {contextforge_id} -> {fam_id}")

    async def start(self) -> None:
        """Start the orchestrator and begin activity execution."""
        if self._running:
            logger.warning("ActivityOrchestrator already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("ActivityOrchestrator started")

    async def stop(self) -> None:
        """Stop the orchestrator and cancel all activities."""
        if not self._running:
            logger.warning("ActivityOrchestrator not running")
            return

        self._running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info("ActivityOrchestrator stopped")

    async def _run_loop(self) -> None:
        """Main execution loop for activities.

        Continuously checks and executes activities that are due.
        Runs every second to check activity schedules.

        IMPORTANT: Enforces dependency that servers must sync before tools,
        because tools need the FAM server ID as mcpServerId.
        """
        logger.info("ActivityOrchestrator execution loop started")

        while self._running:
            try:
                # Reset server sync flag at start of each cycle
                self._servers_synced_this_cycle = False

                # Execute activities in dependency order
                for activity in self.activities:
                    if activity.should_execute():
                        # Special handling for tool sync - must wait for server sync
                        if activity == self.tool_sync_activity:
                            if not self._servers_synced_this_cycle:
                                logger.debug("Skipping tool sync - waiting for server sync to complete first")
                                continue

                        try:
                            await activity.execute()

                            # Track if servers were synced
                            if activity == self.server_sync_activity:
                                self._servers_synced_this_cycle = True
                                logger.debug("Server sync completed - tools can now sync")

                        except Exception as e:
                            logger.error(f"Error executing activity {activity.__class__.__name__}: {e}", exc_info=True)

                # Sleep for 1 second before next check
                await asyncio.sleep(1)

            except asyncio.CancelledError:
                logger.info("ActivityOrchestrator execution loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in orchestrator execution loop: {e}", exc_info=True)
                await asyncio.sleep(5)  # Back off on error

    async def trigger_recovery(self) -> None:
        """Trigger recovery of missed operations.

        Called after runtime registration to recover any missed
        heartbeats, metrics, or asset syncs.
        """
        try:
            logger.info("Triggering recovery of missed operations...")
            await self.recovery_handler.perform_recovery()
            logger.info("Recovery completed successfully")
        except Exception as e:
            logger.error(f"Error during recovery: {e}", exc_info=True)

    def get_statistics(self) -> SyncStatistics:
        """Get aggregated statistics from all activities.

        Returns:
            SyncStatistics with aggregated metrics from all activities
        """
        stats = SyncStatistics(runtime_id=self.runtime_id)

        # Aggregate activity statistics
        for activity in self.activities:
            activity_stats = activity.get_statistics()
            stats.activities[activity.__class__.__name__] = activity_stats

        # Get specific counts from activities (handle optional activities)
        stats.total_heartbeats_sent = self.heartbeat_activity.get_heartbeat_stats().get("total_sent", 0)
        stats.total_metrics_sent = self.metrics_activity.get_metrics_stats().get("total_sent", 0) if self.metrics_activity else 0
        stats.total_servers_synced = self.server_sync_activity.get_sync_stats().get("total_synced", 0) if self.server_sync_activity else 0
        stats.total_tools_synced = self.tool_sync_activity.get_sync_stats().get("total_synced", 0) if self.tool_sync_activity else 0

        return stats

    def get_activity_statistics(self) -> Dict[str, Dict[str, Any]]:
        """Get individual statistics for each activity.

        Returns:
            Dictionary mapping activity names to their statistics
        """
        return {activity.__class__.__name__: activity.get_statistics().model_dump() for activity in self.activities}

    def get_health_status(self) -> Dict[str, Any]:
        """Get health status of the orchestrator and all activities.

        Returns:
            Dictionary with health status information
        """
        stats = self.get_statistics()
        activity_stats = self.get_activity_statistics()

        status: Dict[str, Any] = {
            "running": self._running,
            "total_activities": len(self.activities),
            "overall_statistics": stats.to_dict(),
            "activity_statistics": activity_stats,
            "health_checks": {"fam": self.fam_health_activity.get_health_stats(), "runtime": self.runtime_health_activity.get_health_stats()},
            "heartbeat_status": self.heartbeat_activity.get_heartbeat_stats(),
        }

        # Add optional activity statuses
        if self.metrics_activity:
            status["metrics_status"] = self.metrics_activity.get_metrics_stats()
        if self.server_sync_activity:
            status["server_sync_status"] = self.server_sync_activity.get_sync_stats()
        if self.tool_sync_activity:
            status["tool_sync_status"] = self.tool_sync_activity.get_sync_stats()

        return status


# Made with Bob
