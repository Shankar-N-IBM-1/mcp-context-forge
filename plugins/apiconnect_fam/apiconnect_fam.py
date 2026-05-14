"""API Connect FAM Plugin for ContextForge.

Integrates ContextForge with webMethods API Control Plane FAM (Federated API Management).
Syncs servers, tools, and metrics to FAM Asset Catalog API.

Features:
- Runtime registration with FAM
- Periodic heartbeat to maintain connection
- Server and tool synchronization with change detection
- Bulk operations for efficient syncing
- Metrics synchronization
- Activity-based architecture following webMethods Agent SDK patterns
- Automatic recovery of missed operations after downtime
- Status 409 (Conflict) handling for existing runtimes

Copyright 2025
SPDX-License-Identifier: Apache-2.0
"""

import asyncio
import logging
from typing import List, Optional

from mcpgateway.plugins.framework import Plugin, PluginConfig
from pydantic import BaseModel, Field

from .activity_orchestrator import ActivityOrchestrator
from .fam import FAMAssetCatalogClient

logger = logging.getLogger(__name__)


class APIConnectFAMConfig(BaseModel):
    """Configuration for API Connect FAM plugin.
    
    Attributes:
        interval_seconds: How often to sync servers (in seconds).
        log_details: Whether to log detailed server information.
        fam_enabled: Whether to sync servers to FAM.
        fam_base_url: Base URL for FAM API (e.g., https://fam.example.com).
        fam_runtime_id: Runtime ID to use when syncing to FAM (REQUIRED when fam_enabled is true).
        fam_username: FAM username for Basic Authentication.
        fam_password: FAM password for Basic Authentication.
        fam_timeout: HTTP request timeout in seconds.
        fam_verify_ssl: Whether to verify SSL certificates (set False for self-signed certs).
        fam_asset_sync_enabled: Whether to sync assets (servers/tools) to FAM.
        fam_asset_sync_interval: How often to sync assets (in seconds).
        metrics_sync_enabled: Whether to sync metrics to FAM.
        metrics_sync_interval: How often to sync metrics (in seconds). Also used as time window for metrics collection.
        fam_runtime_name: Runtime display name (for reference only).
        fam_runtime_description: Runtime description (for reference only).
        fam_runtime_type: Runtime type (for reference only).
        fam_runtime_deployment_type: Deployment type (for reference only).
        fam_runtime_region: Region identifier (for reference only).
        fam_runtime_location: Location description (for reference only).
        fam_runtime_host: Host identifier (for reference only).
        fam_runtime_tags: List of tags for the runtime (for reference only).
        fam_runtime_capacity_value: Capacity value (for reference only).
        fam_runtime_capacity_unit: Capacity unit (for reference only).
        fam_runtime_heartbeat_interval: Heartbeat sync interval in milliseconds (for reference only).
        fam_heartbeat_interval_seconds: How often to send heartbeats (in seconds, mandatory when FAM enabled).
    """

    interval_seconds: int = 60
    log_details: bool = True
    fam_enabled: bool = False
    fam_base_url: Optional[str] = Field(default=None, description="FAM API base URL")
    fam_runtime_id: Optional[str] = Field(default=None, description="FAM runtime ID (REQUIRED when fam_enabled is true)")
    fam_username: Optional[str] = Field(default=None, description="FAM username for Basic Authentication")
    fam_password: Optional[str] = Field(default=None, description="FAM password for Basic Authentication")
    fam_timeout: int = 30
    fam_verify_ssl: bool = True  # Verify SSL certificates by default
    fam_asset_sync_enabled: bool = True
    fam_asset_sync_interval: int = 60  # Sync assets every 60 seconds
    metrics_sync_enabled: bool = False
    metrics_sync_interval: int = 300  # 5 minutes default
    
    # Runtime metadata (for reference only, not used after initial registration)
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
    fam_runtime_heartbeat_interval_seconds: int = 60  # Heartbeat interval in seconds (converted to ms for FAM, also used for activity interval)


class APIConnectFAMPlugin(Plugin):
    """API Connect FAM integration plugin - syncs servers, tools, and metrics to FAM.
    
    The plugin delegates all sync operations to the orchestrator, which
    manages activity execution, scheduling, statistics, and recovery.
    """

    def __init__(self, config: PluginConfig) -> None:
        """Initialize the server monitor plugin.

        Args:
            config: Plugin configuration.
        """
        super().__init__(config)
        self._cfg = APIConnectFAMConfig(**(config.config or {}))
        
        # FAM client and orchestrator
        self._fam_client: Optional[FAMAssetCatalogClient] = None
        self._orchestrator: Optional[ActivityOrchestrator] = None
        self._runtime_id: Optional[str] = None

    async def initialize(self) -> None:
        """Start the activity orchestrator and HTTP client."""
        logger.info(f"Initializing APIConnectFAMPlugin with interval={self._cfg.interval_seconds}s")
        
        # Initialize FAM client if sync is enabled
        if self._cfg.fam_enabled:
            # Check if we have all required fields: base URL, username, password, and runtime_id
            if not all([self._cfg.fam_base_url, self._cfg.fam_username, self._cfg.fam_password, self._cfg.fam_runtime_id]):
                error_msg = "FAM sync enabled but required fields missing (base_url, username, password, or runtime_id). Plugin initialization failed."
                logger.error(error_msg)
                raise ValueError(error_msg)
            
            # Store runtime ID
            self._runtime_id = self._cfg.fam_runtime_id
            
            # Create FAM client with runtime ID (type assertions safe due to validation above)
            assert self._cfg.fam_base_url is not None
            assert self._runtime_id is not None
            assert self._cfg.fam_username is not None
            assert self._cfg.fam_password is not None
            
            self._fam_client = FAMAssetCatalogClient(
                base_url=self._cfg.fam_base_url,
                runtime_id=self._runtime_id,
                username=self._cfg.fam_username,
                password=self._cfg.fam_password,
                timeout=self._cfg.fam_timeout,
                verify_ssl=self._cfg.fam_verify_ssl
            )
            
            print(f"\n{'#'*80}")
            print(f"# API Connect FAM Plugin - Initialization")
            print(f"{'#'*80}")
            print(f"[PLUGIN] FAM Base URL: {self._cfg.fam_base_url}")
            print(f"[PLUGIN] Runtime ID: {self._runtime_id}")
            print(f"[PLUGIN] Asset Sync: {'Enabled' if self._cfg.fam_asset_sync_enabled else 'Disabled'}")
            print(f"[PLUGIN] Metrics Sync: {'Enabled' if self._cfg.metrics_sync_enabled else 'Disabled'}")
            print(f"[PLUGIN] Circuit Breaker: Enabled (default)")
            print(f"{'#'*80}\n")
            
            logger.info(f"FAM sync enabled - HTTP client initialized with runtime_id={self._runtime_id}")
            
            # Check FAM health before attempting registration
            print(f"\n[PLUGIN] Checking FAM API health...")
            logger.info("Performing pre-initialization FAM health check")
            
            try:
                is_healthy = await self._fam_client.check_health()
                if not is_healthy:
                    error_msg = "FAM health check failed - API is not responding. Cannot proceed with initialization."
                    print(f"[PLUGIN] ✗ {error_msg}")
                    logger.error(error_msg)
                    raise ValueError(error_msg)
                
                print(f"[PLUGIN] ✓ FAM API is healthy and reachable")
                logger.info("FAM health check passed - proceeding with runtime registration")
                
            except Exception as e:
                error_msg = f"FAM health check failed: {e}"
                print(f"[PLUGIN] ✗ {error_msg}")
                logger.error(error_msg, exc_info=True)
                raise ValueError(error_msg)
            
            # Register/re-register runtime in FAM
            print(f"\n[PLUGIN] Registering runtime with FAM...")
            logger.info(f"Registering runtime in FAM: {self._runtime_id}")
            
            try:
                # Register runtime with configuration-based capabilities
                report = await self._fam_client.register_runtime(
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
                    heartbeat_interval=self._cfg.fam_runtime_heartbeat_interval_seconds,  # Send in seconds
                    publish_assets=self._cfg.fam_asset_sync_enabled,
                    sync_assets=self._cfg.fam_asset_sync_enabled,
                    send_metrics=self._cfg.metrics_sync_enabled
                )
                
                if not report:
                    error_msg = f"Failed to register runtime {self._runtime_id} in FAM"
                    logger.error(error_msg)
                    raise ValueError(error_msg)
                
                # Determine if this is first-time registration or re-registration
                is_reregistration = report.is_reregistration()
                status_text = "re-registered" if is_reregistration else "registered"
                
                print(f"[PLUGIN] ✓ Runtime {status_text} successfully")
                print(f"[PLUGIN]   Status Code: {report.status_code}")
                if report.last_heartbeat_time:
                    print(f"[PLUGIN]   Last Heartbeat: {report.last_heartbeat_time}")
                if report.last_metrics_time:
                    print(f"[PLUGIN]   Last Metrics: {report.last_metrics_time}")
                if report.last_asset_sync_time:
                    print(f"[PLUGIN]   Last Asset Sync: {report.last_asset_sync_time}")
                
                logger.info(f"Runtime {self._runtime_id} {status_text} in FAM, report: {report.model_dump()}")
                
            except Exception as e:
                error_msg = f"Failed to register runtime: {e}"
                logger.error(error_msg, exc_info=True)
                raise ValueError(error_msg)
            
            # Initialize activity orchestrator
            self._orchestrator = ActivityOrchestrator(
                fam_client=self._fam_client,
                runtime_id=self._runtime_id,
                fam_base_url=self._cfg.fam_base_url,
                config=self._cfg.model_dump(),
                heartbeat_interval=self._cfg.fam_runtime_heartbeat_interval_seconds,
                metrics_interval=self._cfg.metrics_sync_interval if self._cfg.metrics_sync_enabled else 0,
                server_sync_interval=self._cfg.fam_asset_sync_interval if self._cfg.fam_asset_sync_enabled else 0,
                tool_sync_interval=self._cfg.fam_asset_sync_interval if self._cfg.fam_asset_sync_enabled else 0
            )
            
            # Mark runtime as registered (enables server and tool sync)
            self._orchestrator.mark_runtime_registered()
            print(f"[PLUGIN] ✓ Runtime registration complete - server and tool sync enabled")
            logger.info("Runtime registration complete - server and tool sync enabled")
            
            # Start orchestrator
            print(f"\n[PLUGIN] Starting activity orchestrator...")
            await self._orchestrator.start()
            print(f"[PLUGIN] ✓ Activity orchestrator started")
            logger.info("Activity orchestrator started")
            
            # Trigger recovery asynchronously only if this is a re-registration (status 200)
            if report and report.is_reregistration():
                status_msg = "status 200" if report.status_code == 200 else f"status {report.status_code} (conflict)"
                print(f"\n[PLUGIN] Re-registration detected ({status_msg})")
                print(f"[PLUGIN] Scheduling recovery of missed operations...")
                logger.info(f"Re-registration detected ({status_msg}) - scheduling recovery of missed operations...")
                
                # Schedule recovery to run asynchronously (don't block initialization)
                asyncio.create_task(self._trigger_recovery_async())
            else:
                print(f"\n[PLUGIN] First-time registration - no recovery needed")
                logger.info("First-time registration (status 201) - no recovery needed")
            
            print(f"\n{'#'*80}")
            print(f"# API Connect FAM Plugin - Ready")
            print(f"{'#'*80}\n")

    async def _trigger_recovery_async(self) -> None:
        """Trigger recovery of missed operations asynchronously.
        
        This method is called after re-registration to recover any missed
        heartbeats, metrics, or asset syncs that occurred during downtime.
        """
        try:
            if self._orchestrator:
                await self._orchestrator.trigger_recovery()
                logger.info("Recovery completed successfully")
        except Exception as e:
            logger.error(f"Error during recovery: {e}", exc_info=True)

    async def shutdown(self) -> None:
        """Stop the activity orchestrator and close HTTP client."""
        logger.info("Shutting down APIConnectFAMPlugin")
        
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
