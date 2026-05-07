"""Sync Tools Activity.

Syncs MCP tools to FAM Asset Catalog using bulk operations.
Follows webMethods Agent SDK SyncAssetsActivity pattern.

Copyright 2025
SPDX-License-Identifier: Apache-2.0
"""

# Standard
from collections import defaultdict
from typing import Any, Dict, List, Optional, TYPE_CHECKING

# First-Party
from mcpgateway.db import Server, SessionLocal, Tool

# Local
from ..fam_client import FAMAssetCatalogClient, ToolStateTracker
from ..models import ActivityContext
from ..utils import RetryConfig, SyncError, with_retry
from .base import AbstractScheduledActivity

if TYPE_CHECKING:
    # Local
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
        sync_interval: Interval in seconds
        orchestrator: Reference to orchestrator for getting server ID mapping
    """

    def __init__(self, context: ActivityContext, fam_client: FAMAssetCatalogClient, sync_interval: int = 60, orchestrator: Optional["ActivityOrchestrator"] = None):
        """Initialize sync tools activity.

        Args:
            context: Shared activity context
            fam_client: FAM API client
            sync_interval: Sync interval in seconds
            orchestrator: Reference to orchestrator (for getting server ID mapping)
        """
        super().__init__(context)
        self._fam_client = fam_client
        self._sync_interval = sync_interval
        self._orchestrator = orchestrator
        self._state_tracker = ToolStateTracker()
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
            print(f"🔄 [FAM Tool Sync] Syncing tools to FAM...")
            
            # Query and sync tools
            tools_synced = await with_retry(self._query_and_sync_tools, retry_config=RetryConfig(max_attempts=2, initial_delay=1.0), operation_name="Sync Tools")

            # Track success
            self._total_tools_synced += tools_synced

            print(f"✅ [FAM Tool Sync] Synced {tools_synced} tools (total: {self._total_tools_synced})")
            self.logger.info(f"Synced {tools_synced} tools to FAM (total: {self._total_tools_synced})")

        except Exception as e:
            error_msg = f"Failed to sync tools: {e}"
            print(f"❌ [FAM Tool Sync] {error_msg}")
            self.logger.error(error_msg, exc_info=True)
            raise SyncError(error_msg, e)

    async def _query_and_sync_tools(self) -> int:
        """Query tools from database and sync to FAM using bulk operations.

        Returns:
            Number of tools synced

        Raises:
            Exception: If query or sync fails
        """
        with SessionLocal() as db:
            tools = db.query(Tool).all()
            servers = db.query(Server).all()

            if not tools:
                self.logger.debug("No tools to sync")
                return 0

            # Get server ID mapping from orchestrator (ContextForge ID -> FAM ID)
            server_id_mapping = {}
            if self._orchestrator:
                server_id_mapping = self._orchestrator.get_server_id_mapping()

            # Build tool-to-server mapping
            tool_to_server = self._build_tool_server_mapping(servers, server_id_mapping)

            # Group tools by server and operation type
            tools_by_server = self._group_tools_by_server_and_operation(tools, tool_to_server)

            total_synced = 0

            # Process each server's tools in bulk
            for server_id, operations in tools_by_server.items():
                # Bulk delete
                if operations["delete"]:
                    job_id = await self._fam_client.bulk_delete_tools(operations["delete"], server_id)
                    if job_id:
                        for tool_id in operations["delete"]:
                            self._state_tracker.mark_deleted(tool_id)
                        total_synced += len(operations["delete"])
                        self.logger.info(f"Bulk deleted {len(operations['delete'])} tools " f"(server: {server_id}, job: {job_id})")

                # Bulk create
                if operations["create"]:
                    job_id = await self._fam_client.bulk_create_tools(operations["create"], server_id)
                    if job_id:
                        for tool in operations["create"]:
                            tool_id = str(tool.id)
                            current_hash = self._state_tracker.compute_hash(tool)
                            self._state_tracker.mark_synced(tool_id, current_hash)
                        total_synced += len(operations["create"])
                        self.logger.info(f"Bulk created {len(operations['create'])} tools " f"(server: {server_id}, job: {job_id})")

                # Bulk update
                if operations["update"]:
                    job_id = await self._fam_client.bulk_update_tools(operations["update"], server_id)
                    if job_id:
                        for tool in operations["update"]:
                            tool_id = str(tool.id)
                            current_hash = self._state_tracker.compute_hash(tool)
                            self._state_tracker.mark_synced(tool_id, current_hash)
                        total_synced += len(operations["update"])
                        self.logger.info(f"Bulk updated {len(operations['update'])} tools " f"(server: {server_id}, job: {job_id})")

            return total_synced

    def _build_tool_server_mapping(self, servers: List[Any], server_id_mapping: Dict[str, str]) -> Dict[str, str]:
        """Build mapping from tool ID to FAM server ID.

        Args:
            servers: List of Server ORM objects
            server_id_mapping: Mapping from ContextForge server ID to FAM server ID

        Returns:
            Dict mapping tool_id to FAM server_id
        """
        tool_to_server = {}
        for server in servers:
            contextforge_server_id = str(server.id)
            fam_server_id = server_id_mapping.get(contextforge_server_id)

            if not fam_server_id:
                # Server not yet synced to FAM, skip its tools
                continue

            if hasattr(server, "tools") and server.tools:
                for tool in server.tools:
                    tool_to_server[str(tool.id)] = fam_server_id

        return tool_to_server

    def _group_tools_by_server_and_operation(self, tools: List[Any], tool_to_server: Dict[str, str]) -> Dict[str, Dict[str, List]]:
        """Group tools by server and operation type (create/update/delete).

        Args:
            tools: List of Tool ORM objects
            tool_to_server: Mapping from tool ID to FAM server ID

        Returns:
            Dict mapping server_id to operations dict with create/update/delete lists
        """
        # Initialize structure: {server_id: {create: [], update: [], delete: []}}
        tools_by_server: Dict[str, Dict[str, List]] = defaultdict(lambda: {"create": [], "update": [], "delete": []})

        current_tool_ids = {str(tool.id) for tool in tools}

        # Detect deleted tools
        deleted_ids = self._state_tracker.get_deleted_tools(current_tool_ids)
        for tool_id in deleted_ids:
            server_id = tool_to_server.get(tool_id)
            if server_id:
                tools_by_server[server_id]["delete"].append(tool_id)

        # Classify current tools
        for tool in tools:
            tool_id = str(tool.id)
            server_id = tool_to_server.get(tool_id)

            if not server_id:
                # Tool not associated with any synced server, skip
                continue

            current_hash = self._state_tracker.compute_hash(tool)

            if self._state_tracker.is_new_tool(tool_id):
                tools_by_server[server_id]["create"].append(tool)
            elif self._state_tracker.has_changed(tool_id, current_hash):
                tools_by_server[server_id]["update"].append(tool)

        return dict(tools_by_server)

    def get_sync_stats(self) -> dict:
        """Get sync statistics.

        Returns:
            Dictionary with sync stats
        """
        return {"total_synced": self._total_tools_synced, "interval_seconds": self._sync_interval, "last_execution": (self.last_execution_time if self.last_execution_time else None)}


# Made with Bob
