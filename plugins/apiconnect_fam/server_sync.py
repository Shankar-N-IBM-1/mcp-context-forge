"""Server Synchronization Module.

Handles synchronization of MCP Servers to FAM Asset Catalog.

Copyright 2025
SPDX-License-Identifier: Apache-2.0
"""

import logging
from typing import Any, List, Set

from mcpgateway.db import Server, SessionLocal

from .activities.sync_servers import ServerStateTracker
from .fam import FAMAssetCatalogClient

logger = logging.getLogger(__name__)


class ServerSyncTask:
    """Task for synchronizing servers to FAM.
    
    Handles:
    - Querying servers from database
    - Detecting new, changed, and deleted servers
    - Creating, updating, and deleting servers in FAM
    - Maintaining sync state
    """
    
    def __init__(self, fam_client: FAMAssetCatalogClient):
        """Initialize server sync task.
        
        Args:
            fam_client: FAM API client for server operations
        """
        self._fam_client = fam_client
        self._state_tracker = ServerStateTracker()
    
    async def execute(self) -> None:
        """Execute server synchronization task.
        
        Queries all servers from database and syncs changes to FAM.
        """
        try:
            with SessionLocal() as db:
                servers = db.query(Server).all()
                await self._sync_servers(servers)
        except Exception as e:
            logger.error(f"Error in server sync task: {e}", exc_info=True)
    
    async def _sync_servers(self, servers: List[Any]) -> None:
        """Sync all servers to FAM by detecting changes.
        
        Uses ServerStateTracker to detect:
        - New servers (not in FAM) → create
        - Changed servers (different hash) → update
        - Deleted servers (in FAM but not in DB) → delete
        
        Args:
            servers: List of Server ORM objects from database
        """
        current_server_ids = {str(server.id) for server in servers}
        
        # Detect and delete servers that no longer exist
        deleted_ids = self._state_tracker.get_deleted_entities(current_server_ids)
        for server_id in deleted_ids:
            if await self._fam_client.delete_server(server_id):
                self._state_tracker.mark_deleted(server_id)
        
        # Process current servers
        for server in servers:
            server_id = str(server.id)
            current_hash = self._state_tracker.compute_hash(server)
            
            if self._state_tracker.is_new_server(server_id):
                # New server - create in FAM
                if await self._fam_client.create_server(server):
                    self._state_tracker.mark_synced(server_id, current_hash)
                    
            elif self._state_tracker.has_changed(server_id, current_hash):
                # Server changed - update in FAM
                if await self._fam_client.update_server(server):
                    self._state_tracker.mark_synced(server_id, current_hash)
    
    def get_stats(self) -> dict:
        """Get synchronization statistics.
        
        Returns:
            Dict with sync statistics
        """
        return {
            "synced_servers": len(self._state_tracker._cache),
            "cached_hashes": len(self._state_tracker._cache)
        }