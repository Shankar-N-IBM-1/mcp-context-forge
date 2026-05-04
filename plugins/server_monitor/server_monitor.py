"""Server Monitor Plugin for ContextForge.

Periodically monitors all virtual servers in the ContextForge system and optionally
syncs them to FAM (Federated API Management) Asset Catalog API.

Features:
- Periodic server monitoring with configurable intervals
- Detailed logging of server information
- FAM synchronization with change detection
- Smart sync operations (create/update/delete)
- Metrics synchronization
- Activity-based architecture following webMethods Agent SDK patterns
- Automatic recovery of missed operations after downtime

Copyright 2025
SPDX-License-Identifier: Apache-2.0
"""

import logging
from typing import Any, Dict, List, Optional

from mcpgateway.plugins.framework import Plugin, PluginConfig
from pydantic import BaseModel, Field

from .activity_orchestrator import ActivityOrchestrator
from .fam_client import FAMAssetCatalogClient
from .models import ReregistrationReport

logger = logging.getLogger(__name__)


class ServerMonitorConfig(BaseModel):
    """Configuration for Server Monitor plugin.
    
    Attributes:
        interval_seconds: How often to sync servers (in seconds).
        log_details: Whether to log detailed server information.
        fam_enabled: Whether to sync servers to FAM.
        fam_base_url: Base URL for FAM API (e.g., https://fam.example.com).
        fam_runtime_id: Runtime ID to use when syncing to FAM (optional if auto_register is true).
        fam_auth_token: Bearer token for FAM API authentication.
        fam_timeout: HTTP request timeout in seconds.
        metrics_sync_enabled: Whether to sync metrics to FAM.
        metrics_sync_interval: How often to sync metrics (in seconds). Also used as time window for metrics collection.
        fam_auto_register: Whether to auto-register runtime on plugin startup.
        fam_runtime_name: Runtime display name for auto-registration.
        fam_runtime_description: Runtime description for auto-registration.
        fam_runtime_type: Runtime type (e.g., WEBMETHODS_GATEWAY).
        fam_runtime_deployment_type: Deployment type (e.g., ON_PREMISE, CLOUD).
        fam_runtime_region: Region identifier (e.g., us-east-1).
        fam_runtime_location: Location description (e.g., US East).
        fam_runtime_host: Host identifier.
        fam_runtime_tags: List of tags for the runtime.
        fam_runtime_capacity_value: Capacity value (e.g., "50").
        fam_runtime_capacity_unit: Capacity unit (e.g., "per minute").
        fam_runtime_heartbeat_interval: Heartbeat sync interval in milliseconds.
        fam_heartbeat_enabled: Whether to enable runtime heartbeat.
        fam_heartbeat_interval_seconds: How often to send heartbeats (in seconds).
    """

    interval_seconds: int = 60
    log_details: bool = True
    fam_enabled: bool = False
    fam_base_url: Optional[str] = Field(default=None, description="FAM API base URL")
    fam_runtime_id: Optional[str] = Field(default=None, description="FAM runtime ID (optional if auto_register is true)")
    fam_auth_token: Optional[str] = Field(default=None, description="FAM auth token")
    fam_timeout: int = 30
    metrics_sync_enabled: bool = False
    metrics_sync_interval: int = 300  # 5 minutes default
    
    # Runtime auto-registration configuration
    fam_auto_register: bool = True
    fam_runtime_name: str = "ContextForge Gateway"
    fam_runtime_description: str = "ContextForge MCP Gateway Runtime"
    fam_runtime_type: str = "WEBMETHODS_GATEWAY"
    fam_runtime_deployment_type: str = "ON_PREMISE"
    fam_runtime_region: Optional[str] = Field(default=None, description="Runtime region")
    fam_runtime_location: Optional[str] = Field(default=None, description="Runtime location")
    fam_runtime_host: Optional[str] = Field(default=None, description="Runtime host identifier")
    fam_runtime_tags: List[str] = Field(default_factory=lambda: ["contextforge", "mcp"])
    fam_runtime_capacity_value: str = "100"
    fam_runtime_capacity_unit: str = "per minute"
    fam_runtime_heartbeat_interval: int = 6000
    
    # Heartbeat configuration
    fam_heartbeat_enabled: bool = True
    fam_heartbeat_interval_seconds: int = 60  # Send heartbeat every 60 seconds


class ServerMonitorPlugin(Plugin):
    """Monitors and periodically syncs virtual servers to FAM.
    
    This plugin uses an activity-based architecture following webMethods Agent SDK patterns:
    - ActivityOrchestrator: Coordinates all activities
    - SendHeartbeatActivity: Sends periodic heartbeats
    - SendMetricsActivity: Syncs metrics data
    - SyncServersActivity: Syncs server assets
    - SyncToolsActivity: Syncs tool assets
    - RecoveryHandler: Automatically recovers missed operations after downtime
    
    The plugin delegates all sync operations to the orchestrator, which
    manages activity execution, scheduling, statistics, and recovery.
    """

    def __init__(self, config: PluginConfig) -> None:
        """Initialize the server monitor plugin.

        Args:
            config: Plugin configuration.
        """
        super().__init__(config)
        self._cfg = ServerMonitorConfig(**(config.config or {}))
        
        # FAM client and orchestrator
        self._fam_client: Optional[FAMAssetCatalogClient] = None
        self._orchestrator: Optional[ActivityOrchestrator] = None
        self._runtime_id: Optional[str] = None

    async def initialize(self) -> None:
        """Start the activity orchestrator and HTTP client."""
        logger.info(f"Initializing ServerMonitorPlugin with interval={self._cfg.interval_seconds}s")
        
        # Initialize FAM client if sync is enabled
        if self._cfg.fam_enabled:
            # Check if we have base URL and auth token (runtime_id is optional if auto_register is true)
            if not all([self._cfg.fam_base_url, self._cfg.fam_auth_token]):
                logger.error("FAM sync enabled but base_url or auth_token missing. Disabling FAM sync.")
                self._cfg.fam_enabled = False
                return
            
            # Determine runtime ID and re-registration report
            runtime_id: Optional[str] = self._cfg.fam_runtime_id
            report: Optional[ReregistrationReport] = None
            
            # Auto-register runtime if enabled and no runtime_id provided
            if self._cfg.fam_auto_register and not runtime_id:
                logger.info("Auto-registering runtime in FAM...")
                
                # Create temporary client for registration (without runtime_id)
                temp_client = FAMAssetCatalogClient(
                    base_url=self._cfg.fam_base_url,
                    runtime_id="temp",  # Placeholder, not used for registration
                    auth_token=self._cfg.fam_auth_token,
                    timeout=self._cfg.fam_timeout
                )
                
                try:
                    # Register runtime and get re-registration report
                    report = await temp_client.register_runtime(
                        name=self._cfg.fam_runtime_name,
                        description=self._cfg.fam_runtime_description,
                        runtime_type=self._cfg.fam_runtime_type,
                        deployment_type=self._cfg.fam_runtime_deployment_type,
                        region=self._cfg.fam_runtime_region,
                        location=self._cfg.fam_runtime_location,
                        host=self._cfg.fam_runtime_host,
                        tags=self._cfg.fam_runtime_tags,
                        capacity_value=self._cfg.fam_runtime_capacity_value,
                        capacity_unit=self._cfg.fam_runtime_capacity_unit,
                        heartbeat_interval=self._cfg.fam_runtime_heartbeat_interval
                    )
                    
                    if report:
                        runtime_id = report.runtime_id
                        logger.info(
                            f"Runtime auto-registered successfully with ID: {runtime_id}, "
                            f"re-registration report: {report.model_dump()}"
                        )
                    else:
                        logger.error("Runtime auto-registration failed - no report returned")
                finally:
                    await temp_client.close()
            
            # Verify we have a runtime ID
            if not runtime_id:
                logger.error("No runtime ID available (auto-registration failed or disabled). Disabling FAM sync.")
                self._cfg.fam_enabled = False
                return
            
            # Store runtime ID
            self._runtime_id = runtime_id
            
            # Create FAM client with runtime ID
            self._fam_client = FAMAssetCatalogClient(
                base_url=self._cfg.fam_base_url,
                runtime_id=runtime_id,
                auth_token=self._cfg.fam_auth_token,
                timeout=self._cfg.fam_timeout
            )
            logger.info(f"FAM sync enabled - HTTP client initialized with runtime_id={runtime_id}")
            
            # Initialize activity orchestrator
            self._orchestrator = ActivityOrchestrator(
                fam_client=self._fam_client,
                runtime_id=runtime_id,
                fam_base_url=self._cfg.fam_base_url,
                fam_auth_token=self._cfg.fam_auth_token,
                config=self._cfg.model_dump(),
                heartbeat_interval=self._cfg.fam_heartbeat_interval_seconds,
                metrics_interval=self._cfg.metrics_sync_interval,
                server_sync_interval=self._cfg.interval_seconds,
                tool_sync_interval=self._cfg.interval_seconds
            )
            
            # Start orchestrator
            await self._orchestrator.start()
            logger.info("Activity orchestrator started")
            
            # Trigger recovery if this is a re-registration (has previous sync timestamps)
            if report and (report.last_heartbeat_time or report.last_metrics_time or report.last_asset_sync_time):
                logger.info("Re-registration detected - triggering recovery of missed operations...")
                try:
                    await self._orchestrator.trigger_recovery()
                    logger.info("Recovery completed successfully")
                except Exception as e:
                    logger.error(f"Error during recovery: {e}", exc_info=True)

    async def shutdown(self) -> None:
        """Stop the activity orchestrator and close HTTP client."""
        logger.info("Shutting down ServerMonitorPlugin")
        
        # Stop orchestrator
        if self._orchestrator:
            await self._orchestrator.stop()
            logger.info("Activity orchestrator stopped")
        
        # Close FAM client
        if self._fam_client:
            await self._fam_client.close()
            self._fam_client = None
            logger.info("FAM client closed")

# Made with Bob
