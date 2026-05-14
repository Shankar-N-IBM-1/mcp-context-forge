"""API Connect FAM Plugin for ContextForge.

Integrates ContextForge with webMethods API Control Plane FAM (Federated API Management).
Syncs servers, tools, and metrics to FAM Asset Catalog API.

Features:
- Runtime registration with FAM
- Periodic heartbeat to maintain connection
- Server and tool synchronization with change detection
- Metrics synchronization
"""

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
            
            # Start orchestrator (will perform registration first, then start activities)
            print(f"\n[PLUGIN] Starting activity orchestrator...")
            await self._orchestrator.start()
            print(f"[PLUGIN] ✓ Activity orchestrator started")
            logger.info("Activity orchestrator started")
            
            print(f"\n{'#'*80}")
            print(f"# API Connect FAM Plugin - Ready")
            print(f"{'#'*80}\n")

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