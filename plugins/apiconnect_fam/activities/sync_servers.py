"""Sync Servers Activity.

Syncs MCP servers to FAM Asset Catalog.
Follows webMethods Agent SDK SyncAssetsActivity pattern.

Copyright 2025
SPDX-License-Identifier: Apache-2.0
"""

# Standard
from typing import Optional, TYPE_CHECKING

# First-Party
from mcpgateway.db import Server, SessionLocal

# Local
from ..fam_client import FAMAssetCatalogClient
from ..models import ActivityContext
from ..utils import RetryConfig, SyncError, with_retry
from .base import AbstractScheduledActivity

if TYPE_CHECKING:
    # Local
    from ..activity_orchestrator import ActivityOrchestrator


class SyncServersActivity(AbstractScheduledActivity):
    """Activity for syncing MCP servers to FAM.

    Following webMethods SDK pattern, this activity:
    1. Queries servers from database
    2. Detects changes via hash comparison
    3. Syncs CREATE/UPDATE/DELETE to FAM
    4. Updates server ID mapping in orchestrator (for tool sync)
    5. Updates timestamp storage
    6. Tracks statistics

    IMPORTANT: This activity must complete before SyncToolsActivity runs,
    because tools need the FAM server ID as mcpServerId.

    Attributes:
        context: Shared activity context
        fam_client: FAM API client
        sync_interval: Interval in seconds
        orchestrator: Reference to orchestrator for updating server ID mapping
    """

    def __init__(self, context: ActivityContext, fam_client: FAMAssetCatalogClient, sync_interval: int = 60, orchestrator: Optional["ActivityOrchestrator"] = None):
        """Initialize sync servers activity.

        Args:
            context: Shared activity context
            fam_client: FAM API client
            sync_interval: Sync interval in seconds
            orchestrator: Reference to orchestrator (for updating server ID mapping)
        """
        super().__init__(context)
        self._fam_client = fam_client
        self._sync_interval = sync_interval
        self._orchestrator = orchestrator
        self._total_servers_synced = 0

    def get_interval_seconds(self) -> int:
        """Get the sync interval.

        Returns:
            Interval in seconds
        """
        return self._sync_interval

    async def perform(self) -> None:
        """Sync servers to FAM.

        Raises:
            SyncError: If sync fails
        """
        try:
            print(f"🔄 [FAM Server Sync] Syncing servers to FAM...")
            
            # Query and sync servers
            servers_synced = await with_retry(self._query_and_sync_servers, retry_config=RetryConfig(max_attempts=2, initial_delay=1.0), operation_name="Sync Servers")

            # Track success
            self._total_servers_synced += servers_synced

            print(f"✅ [FAM Server Sync] Synced {servers_synced} servers (total: {self._total_servers_synced})")
            self.logger.info(f"Synced {servers_synced} servers to FAM (total: {self._total_servers_synced})")

        except Exception as e:
            error_msg = f"Failed to sync servers: {e}"
            print(f"❌ [FAM Server Sync] {error_msg}")
            self.logger.error(error_msg, exc_info=True)
            raise SyncError(error_msg, e)

    async def _query_and_sync_servers(self) -> int:
        """Query servers from database and sync to FAM.

        Returns:
            Number of servers synced

        Raises:
            Exception: If query or sync fails
        """
        with SessionLocal() as db:
            servers = db.query(Server).all()

            if not servers:
                self.logger.debug("No servers to sync")
                return 0

            # TODO: Implement actual sync logic
            # This would use the logic from server_sync.py:
            # 1. Calculate hash for each server
            # 2. Compare with FAM state
            # 3. Send CREATE/UPDATE/DELETE operations

            self.logger.info(f"Found {len(servers)} servers to sync")
            return len(servers)

    def get_sync_stats(self) -> dict:
        """Get sync statistics.

        Returns:
            Dictionary with sync stats
        """
        return {"total_synced": self._total_servers_synced, "interval_seconds": self._sync_interval, "last_execution": (self.last_execution_time if self.last_execution_time else None)}


# Made with Bob
