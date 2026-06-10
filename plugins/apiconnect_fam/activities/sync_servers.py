"""Location: ./plugins/apiconnect_fam/activities/sync_servers.py
Copyright 2026
SPDX-License-Identifier: Apache-2.0
Authors: Shankar N

Sync Servers Activity.

Syncs MCP servers to FAM Asset Catalog.
"""

# Standard
from typing import Any, List, Optional, TYPE_CHECKING

# First-Party
from mcpgateway.db import Server, SessionLocal

# Local
from ..fam import FAMAssetCatalogClient
from ..models import ActivityContext
from ..utils import RetryConfig, SyncError, with_retry
from .base import AbstractScheduledActivity
from .state_tracker import AbstractStateTracker

if TYPE_CHECKING:
    # Local
    from ..activity_orchestrator import ActivityOrchestrator


class ServerStateTracker(AbstractStateTracker):
    """Tracks server state for change detection using content hashing.

    Since server payloads now include both 'id' and 'mcpServerId' with the same value,
    we only need to track content hashes. Server presence in cache = synced to FAM.

    Extends AbstractStateTracker with server-specific hash computation.
    """

    @staticmethod
    def compute_hash(entity: Any) -> str:
        """Compute SHA-256 hash of server content.

        Only includes fields that FAM API accepts (matches FAMServerPayload logic):
        - name (required)
        - description (optional)
        - enabled (maps to status: ACTIVE/INACTIVE)
        - url (optional)
        - tags (optional, sorted for consistency)
        - capabilities (derived from tools/resources/prompts relationships)

        Args:
            entity: ContextForge Server ORM object

        Returns:
            SHA-256 hash string
        """
        # Derive capabilities from relationships (matches FAMServerPayload._get_capabilities)
        capabilities: List[str] = []
        if hasattr(entity, "tools") and entity.tools and len(entity.tools) > 0:
            capabilities.append("TOOLS")
        if hasattr(entity, "resources") and entity.resources and len(entity.resources) > 0:
            capabilities.append("RESOURCES")
        if hasattr(entity, "prompts") and entity.prompts and len(entity.prompts) > 0:
            capabilities.append("PROMPTS")
        
        server_data = {
            "name": entity.name,
            "description": entity.description,
            "enabled": entity.enabled,
            "url": entity.url if hasattr(entity, "url") else None,
            "tags": sorted(entity.tags) if hasattr(entity, "tags") and entity.tags else [],
            "capabilities": sorted(capabilities),  # Sort for consistency
        }
        return AbstractStateTracker._compute_hash_from_dict(server_data)

    def is_new_server(self, server_id: str) -> bool:
        """Check if server is new (not yet synced to FAM).

        Convenience method that delegates to base class is_new().

        Args:
            server_id: Server identifier

        Returns:
            True if server is new (no hash in cache)
        """
        return self.is_new(server_id)


class SyncServersActivity(AbstractScheduledActivity):
    """Activity for syncing MCP servers to FAM.


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
        self._state_tracker = ServerStateTracker()
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
            # Query and sync servers
            servers_synced = await with_retry(self._query_and_sync_servers, retry_config=RetryConfig(max_attempts=2, initial_delay=1.0), operation_name="Sync Servers")

            # Track success
            self._total_servers_synced += servers_synced

            self.logger.info(f"Synced {servers_synced} servers to FAM (total: {self._total_servers_synced})")

        except Exception as e:
            error_msg = f"Failed to sync servers: {e}"
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

            # Get current server IDs
            current_server_ids = {str(server.id) for server in servers}

            # Detect deleted servers
            deleted_server_ids = self._state_tracker.get_deleted_entities(current_server_ids)
            
            # Delete servers from FAM
            for server_id in deleted_server_ids:
                try:
                    self.logger.debug(f"Server {server_id} deleted from DB, deleting from FAM...")
                    success = await self._fam_client.delete_server(server_id)
                    if success:
                        self.logger.debug(f"Server {server_id} deleted from FAM")
                        self._state_tracker.mark_deleted(server_id)
                        # Unmark server in orchestrator
                        if self._orchestrator:
                            self._orchestrator.unmark_server_synced(server_id)
                    else:
                        self.logger.warning(f"Failed to delete server {server_id} from FAM")
                except Exception as e:
                    self.logger.error(f"Error deleting server {server_id}: {e}", exc_info=True)

            synced_count = 0
            for server in servers:
                try:
                    server_id = str(server.id)
                    

                    # Compute hash for change detection
                    current_hash = self._state_tracker.compute_hash(server)

                    # Check if server needs syncing
                    is_new = self._state_tracker.is_new_server(server_id)
                    has_changed = self._state_tracker.has_changed(server_id, current_hash)

                    if is_new:
                        self.logger.debug(f"Server {server_id} is NEW, syncing...")
                    elif has_changed:
                        self.logger.debug(f"Server {server_id} has CHANGED, syncing...")
                    else:
                        self.logger.debug(f"Server {server_id} unchanged, skipping")
                        continue

                    # Try to create server in FAM
                    self.logger.debug("Calling FAM API: POST /api/assetcatalog/v1/runtimes/.../mcp-servers")
                    self.logger.debug(f"Server ID: {server.id}, Name: {server.name}")

                    success = await self._fam_client.create_server(server)

                    if success:
                        self.logger.debug(f"Server created/updated in FAM: {server.id}")
                        # Mark as synced in state tracker
                        self._state_tracker.mark_synced(server_id, current_hash)
                        synced_count += 1

                        # Mark server as synced in orchestrator (for tool sync dependency)
                        if self._orchestrator:
                            self._orchestrator.mark_server_synced(server_id)
                    else:
                        self.logger.warning(f"Failed to sync server: {server.id}")

                except Exception as e:
                    self.logger.error(f"Error syncing server {server.id}: {e}", exc_info=True)

            self.logger.info(f"Synced {synced_count} servers to FAM")
            return synced_count
