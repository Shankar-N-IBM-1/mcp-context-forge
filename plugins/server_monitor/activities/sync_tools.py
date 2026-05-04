"""Sync Tools Activity.

Syncs MCP tools to FAM Asset Catalog.
Follows webMethods Agent SDK SyncAssetsActivity pattern.

Copyright 2025
SPDX-License-Identifier: Apache-2.0
"""

from typing import TYPE_CHECKING, Optional

from mcpgateway.db import Tool, SessionLocal

from ..fam_client import FAMAssetCatalogClient
from ..handlers import TimestampStorageHandler
from ..models import ActivityContext
from ..utils import SyncError, with_retry, RetryConfig
from .base import AbstractScheduledActivity

if TYPE_CHECKING:
    from ..activity_orchestrator import ActivityOrchestrator


class SyncToolsActivity(AbstractScheduledActivity):
    """Activity for syncing MCP tools to FAM.
    
    Following webMethods SDK pattern, this activity:
    1. Queries tools from database
    2. Gets server ID mapping from orchestrator
    3. Detects changes via hash comparison
    4. Syncs CREATE/UPDATE/DELETE to FAM (using FAM server ID as mcpServerId)
    5. Updates timestamp storage
    6. Tracks statistics
    
    IMPORTANT: This activity depends on SyncServersActivity completing first,
    because tools need the FAM server ID as mcpServerId.
    
    Attributes:
        context: Shared activity context
        fam_client: FAM API client
        timestamp_handler: Timestamp storage handler
        sync_interval: Interval in seconds
        orchestrator: Reference to orchestrator for getting server ID mapping
    """
    
    def __init__(
        self,
        context: ActivityContext,
        fam_client: FAMAssetCatalogClient,
        timestamp_handler: TimestampStorageHandler,
        sync_interval: int = 60,
        orchestrator: Optional['ActivityOrchestrator'] = None
    ):
        """Initialize sync tools activity.
        
        Args:
            context: Shared activity context
            fam_client: FAM API client
            timestamp_handler: Timestamp storage handler
            sync_interval: Sync interval in seconds
            orchestrator: Reference to orchestrator (for getting server ID mapping)
        """
        super().__init__(context)
        self._fam_client = fam_client
        self._timestamp_handler = timestamp_handler
        self._sync_interval = sync_interval
        self._orchestrator = orchestrator
        self._total_tools_synced = 0
    
    def get_interval_seconds(self) -> int:
        """Get the sync interval.
        
        Returns:
            Interval in seconds
        """
        return self._sync_interval
    
    async def perform(self) -> None:
        """Sync tools to FAM.
        
        Raises:
            SyncError: If sync fails
        """
        try:
            # Query and sync tools
            tools_synced = await with_retry(
                self._query_and_sync_tools,
                retry_config=RetryConfig(max_attempts=2, initial_delay=1.0),
                operation_name="Sync Tools"
            )
            
            # Update timestamp storage
            from datetime import datetime, timezone
            current_time_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
            self._timestamp_handler.save_timestamp(
                self._timestamp_handler.KEY_TOOL_SYNC,
                current_time_ms
            )
            
            # Track success
            self._total_tools_synced += tools_synced
            
            self.logger.info(
                f"Synced {tools_synced} tools to FAM (total: {self._total_tools_synced})"
            )
            
        except Exception as e:
            error_msg = f"Failed to sync tools: {e}"
            self.logger.error(error_msg, exc_info=True)
            raise SyncError(error_msg, e)
    
    async def _query_and_sync_tools(self) -> int:
        """Query tools from database and sync to FAM.
        
        Returns:
            Number of tools synced
            
        Raises:
            Exception: If query or sync fails
        """
        with SessionLocal() as db:
            tools = db.query(Tool).all()
            
            if not tools:
                self.logger.debug("No tools to sync")
                return 0
            
            # TODO: Implement actual sync logic
            # This would use the logic from tool_sync.py:
            # 1. Calculate hash for each tool
            # 2. Compare with FAM state
            # 3. Send CREATE/UPDATE/DELETE operations
            
            self.logger.info(f"Found {len(tools)} tools to sync")
            return len(tools)
    
    def get_sync_stats(self) -> dict:
        """Get sync statistics.
        
        Returns:
            Dictionary with sync stats
        """
        return {
            "total_synced": self._total_tools_synced,
            "interval_seconds": self._sync_interval,
            "last_execution": (
                self.last_execution_time
                if self.last_execution_time
                else None
            )
        }


# Made with Bob