"""Location: ./plugins/apiconnect_fam/activity_orchestrator.py
Copyright 2026
SPDX-License-Identifier: Apache-2.0
Authors: Shankar N

Activity Orchestrator for Server Monitor Plugin.

Coordinates activity execution, statistics tracking, and health monitoring.
"""

# Standard
import asyncio
import logging
import os
from typing import Any, Dict, List, Optional

# Local
from .activities.base import AbstractScheduledActivity
from .activities.register_runtime import RegisterRuntimeActivity
from .activities.send_heartbeat import SendHeartbeatActivity
from .activities.send_metrics import SendMetricsActivity
from .activities.sync_servers import SyncServersActivity
from .activities.sync_tools import SyncToolsActivity
from .fam import FAMAssetCatalogClient
from .models import ActivityContext

logger = logging.getLogger(__name__)


class ActivityOrchestrator:
    """Orchestrates all activities for the Server Monitor Plugin.

    Manages activity lifecycle, execution scheduling, statistics tracking,
    and health monitoring.

    Attributes:
        context: Shared context for all activities
        fam_client: IBM API Connect Federated API Management API client
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
        """
        # Create shared context
        self.context = ActivityContext(runtime_id=runtime_id, fam_base_url=fam_base_url, config=config)

        self.fam_client = fam_client
        self.runtime_id = runtime_id

        # Extract runtime configuration from plugin config
        runtime_config = {
            "name": config.get("fam_runtime_name", "ContextForge Gateway"),
            "description": config.get("fam_runtime_description", "ContextForge MCP Gateway Runtime"),
            "type": config.get("fam_runtime_type", "MCP_CONTEXT_FORGE"),
            "deployment_type": config.get("fam_runtime_deployment_type", "ON_PREMISE"),
            "region": config.get("fam_runtime_region"),
            "location": config.get("fam_runtime_location"),
            "host": config.get("fam_runtime_host"),
            "tags": config.get("fam_runtime_tags", []),
            "capacity_value": config.get("fam_runtime_capacity_value", "100"),
            "capacity_unit": config.get("fam_runtime_capacity_unit", "per minute"),
            "heartbeat_interval": heartbeat_interval,
        }

        # Create registration activity (executed once during start)
        self.register_activity = RegisterRuntimeActivity(context=self.context, fam_client=fam_client, runtime_config=runtime_config)

        # Initialize scheduled activities
        # Note: Order matters! Servers must sync before tools
        self.activities: List[AbstractScheduledActivity] = []

        # Create heartbeat activity (mandatory)
        self.heartbeat_activity = SendHeartbeatActivity(context=self.context, fam_client=fam_client, heartbeat_interval=heartbeat_interval)
        self.activities.append(self.heartbeat_activity)
        logger.info(f"Heartbeat activity created with interval={heartbeat_interval}s")

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

        # Track if runtime has been registered to FAM
        # Server and tool sync should only happen AFTER runtime registration
        self._runtime_registered = False

        # Orchestrator state
        self._running = False
        self._activity_tasks: Dict[str, asyncio.Task] = {}  # activity_name -> task

        # Shared state for activity coordination
        # Track which servers have been registered to FAM
        # Set of server IDs that have been successfully synced to FAM
        self._registered_servers: set[str] = set()

        logger.info(
            f"ActivityOrchestrator initialized with {len(self.activities)} activities: "
            f"heartbeat={heartbeat_interval}s, metrics={metrics_interval if metrics_interval > 0 else 'disabled'}s, "
            f"servers={server_sync_interval if server_sync_interval > 0 else 'disabled'}s, "
            f"tools={tool_sync_interval if tool_sync_interval > 0 else 'disabled'}s"
        )

    def mark_server_synced(self, server_id: str) -> None:
        """Mark a server as synced to FAM.

        Called by server sync activity when a server is successfully synced to FAM.

        Args:
            server_id: ContextForge server ID
        """
        self._registered_servers.add(server_id)
        logger.debug(f"Server {server_id} marked as synced to FAM")

    def is_server_registered(self, server_id: str) -> bool:
        """Check if a server has been registered to FAM.

        Args:
            server_id: ContextForge server ID

        Returns:
            True if server has been synced to FAM
        """
        return server_id in self._registered_servers

    def get_registered_servers(self) -> set[str]:
        """Get set of all registered server IDs.

        Returns:
            Set of ContextForge server IDs that have been registered to FAM
        """
        return self._registered_servers.copy()

    def mark_runtime_registered(self) -> None:
        """Mark runtime as registered to FAM.

        Called after successful runtime registration.
        Enables server and tool sync activities.
        """
        self._runtime_registered = True
        logger.info("Runtime marked as registered - server and tool sync now enabled")

    def _is_primary_worker(self) -> bool:
        """Check if this is the primary worker.
        
        Returns True if:
        - Not running under Gunicorn (GUNICORN_WORKER_ID not set)
        - Running as worker_id=1 (primary worker)
        
        This check must be done at runtime (in start()), not during plugin
        initialization, because Gunicorn sets GUNICORN_WORKER_ID after
        the plugin's initialize() method runs.
        """
        worker_id = os.environ.get("GUNICORN_WORKER_ID")
        
        if worker_id is None:
            is_primary = True
        else:
            try:
                worker_id_int = int(worker_id)
                is_primary = worker_id_int == 1
            except (ValueError, TypeError) as e:
                is_primary = False
        
        logger.info(f"Worker check: worker_id={worker_id or 'N/A'}, is_primary={is_primary}")
        return is_primary

    async def start(self) -> None:
        """Start the orchestrator and begin activity execution.

        Checks if this is the primary worker before starting activities.
        Only the primary worker (worker_id=1) runs background activities.
        
        Creates a single coordinator task that manages all activity execution.
        """
        
        if self._running:
            logger.warning("ActivityOrchestrator already running")
            return

        # Check if this is the primary worker (must be done here, not in plugin init)
        is_primary = self._is_primary_worker()
        
        if not is_primary:
            worker_id = os.environ.get("GUNICORN_WORKER_ID")
            logger.info(f"Skipping activity orchestrator on non-primary worker (worker_id={worker_id})")
            return

        logger.info("Starting activity orchestrator on primary worker")

        # Execute runtime registration before starting activities
        logger.info("Executing runtime registration activity")

        try:
            await self.register_activity.perform()

            # Mark runtime as registered (enables server and tool sync)
            self._runtime_registered = True
            logger.info("Runtime registration complete - all activities enabled")

        except Exception as e:
            error_msg = f"Runtime registration failed: {e}"
            logger.error(error_msg, exc_info=True)
            raise

        # Start the coordinator task that manages all activities
        self._running = True
        
        # Create single coordinator task
        coordinator_task = asyncio.create_task(self._run_coordinator(), name="activity_coordinator")
        self._activity_tasks["coordinator"] = coordinator_task
        
        logger.info("Activity coordinator task started")
        
        # Give coordinator a moment to start
        await asyncio.sleep(0.1)

    async def stop(self) -> None:
        """Stop the orchestrator and cancel all activity tasks."""
        if not self._running and not self._activity_tasks:
            logger.warning("ActivityOrchestrator not running and no tasks to cancel")
            return

        self._running = False

        # Cancel all activity tasks (even if _running was already False)
        cancelled_count = 0
        for activity_name, task in self._activity_tasks.items():
            if not task.done():
                task.cancel()
                cancelled_count += 1
                logger.info(f"Cancelled activity task: {activity_name}")
        
        # Wait for all tasks to complete cancellation
        if self._activity_tasks:
            await asyncio.gather(*self._activity_tasks.values(), return_exceptions=True)
        
        self._activity_tasks.clear()
        logger.info(f"ActivityOrchestrator stopped - cancelled {cancelled_count} activity tasks")

    async def _run_coordinator(self) -> None:
        """Coordinator task that manages all activity execution.
        
        This single task creates and manages individual activity tasks,
        ensuring they continue running for the lifetime of the application.
        """
        logger.info("Activity coordinator started")
        
        # Create individual activity tasks
        activity_tasks = {}
        for activity in self.activities:
            activity_name = activity.__class__.__name__
            task = asyncio.create_task(
                self._run_activity_loop(activity),
                name=f"activity_{activity_name}"
            )
            activity_tasks[activity_name] = task
        
        logger.info(f"Coordinator managing {len(activity_tasks)} activity tasks")
        
        # Monitor tasks and keep them alive
        try:
            while self._running:
                # Check if any tasks have died and restart them
                for activity_name, task in list(activity_tasks.items()):
                    if task.done():
                        logger.warning(f"Activity task {activity_name} died, restarting")
                        
                        # Find the activity and restart its task
                        activity = next((a for a in self.activities if a.__class__.__name__ == activity_name), None)
                        if activity:
                            new_task = asyncio.create_task(
                                self._run_activity_loop(activity),
                                name=f"activity_{activity_name}"
                            )
                            activity_tasks[activity_name] = new_task
                
                # Sleep before next check
                await asyncio.sleep(120)
        
        except asyncio.CancelledError:
            logger.info("Activity coordinator cancelled")
            # Cancel all activity tasks
            for task in activity_tasks.values():
                task.cancel()
            raise
        
        logger.info("Activity coordinator stopped")

    async def _run_activity_loop(self, activity: Any) -> None:
        """Independent execution loop for a single activity.
        
        Each activity runs in its own task with simple interval-based scheduling.
        Executes immediately on first run, then sleeps for the interval duration.
        
        Args:
            activity: The activity instance to run
        """
        activity_name = activity.__class__.__name__
        interval = activity.get_interval_seconds()
        logger.info(f"Activity scheduler started for: {activity_name} (interval={interval}s)")
        
        # Initial small delay to stagger activity starts (prevents thundering herd)
        await asyncio.sleep(0.1)
        
        while self._running:
            try:
                # Dependency checks for specific activities
                should_skip = False
                skip_reason = ""
                
                # Server sync requires runtime registration
                if activity == self.server_sync_activity:
                    if not self._runtime_registered:
                        should_skip = True
                        skip_reason = "waiting for runtime registration"
                
                # Tool sync requires both runtime registration AND at least one server synced
                elif activity == self.tool_sync_activity:
                    if not self._runtime_registered:
                        should_skip = True
                        skip_reason = "waiting for runtime registration"
                    elif not self._registered_servers:
                        should_skip = True
                        skip_reason = "waiting for at least one server to be synced"
                
                if should_skip:
                    logger.debug(f"Skipping {activity_name} - {skip_reason}")
                else:
                    try:
                        # Execute the activity
                        await activity.execute()
                        logger.debug(f"Activity {activity_name} executed successfully")
                    except Exception as e:
                        logger.error(f"Error executing activity {activity_name}: {e}", exc_info=True)
                
                # Sleep for the interval duration after execution
                await asyncio.sleep(interval)
                
            except asyncio.CancelledError:
                logger.info(f"Activity scheduler cancelled for: {activity_name}")
                break
            except Exception as e:
                logger.error(f"Error in activity scheduler for {activity_name}: {e}", exc_info=True)
                # On error, back off before retrying
                await asyncio.sleep(min(interval, 60))
        
        logger.info(f"Activity scheduler stopped for: {activity_name}")

    async def trigger_recovery(self) -> None:
        """Trigger recovery of missed operations.

        Called after runtime registration to recover any missed
        heartbeats, metrics, or asset syncs.

        TODO: Implement recovery handler
        - Recover missed heartbeats (send INACTIVE heartbeats for missed intervals)
        - Recover missed metrics (send historical metrics data)
        - Recover missed asset syncs (perform full server/tool sync)
        See: handlers/recovery_handler.py for implementation reference
        """
        logger.warning("Recovery handler not implemented - skipping recovery")
