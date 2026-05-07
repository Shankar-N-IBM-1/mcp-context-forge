"""Tool Synchronization Module.

Handles synchronization of MCP Tools to FAM Asset Catalog.

Copyright 2025
SPDX-License-Identifier: Apache-2.0
"""

import logging
from typing import Any, Dict, List

from mcpgateway.db import Server, Tool, SessionLocal

from .fam_client import FAMAssetCatalogClient, ToolStateTracker

logger = logging.getLogger(__name__)


class ToolSyncTask:
    """Task for synchronizing tools to FAM.

    Handles:
    - Querying tools from database
    - Building tool-to-server mapping
    - Detecting new, changed, and deleted tools
    - Creating, updating, and deleting tools in FAM
    - Maintaining sync state
    """

    def __init__(self, fam_client: FAMAssetCatalogClient):
        """Initialize tool sync task.

        Args:
            fam_client: FAM API client for tool operations
        """
        self._fam_client = fam_client
        self._state_tracker = ToolStateTracker()

    async def execute(self) -> None:
        """Execute tool synchronization task.

        Queries all tools and servers from database and syncs changes to FAM.
        """
        try:
            with SessionLocal() as db:
                tools = db.query(Tool).all()
                servers = db.query(Server).all()
                await self._sync_tools(tools, servers)
        except Exception as e:
            logger.error(f"Error in tool sync task: {e}", exc_info=True)

    async def _sync_tools(self, tools: List[Any], servers: List[Any]) -> None:
        """Sync all tools to FAM by detecting changes.

        Args:
            tools: List of Tool ORM objects from database
            servers: List of Server ORM objects (for server-tool mapping)
        """
        # Build tool-to-server mapping
        tool_to_server = self._build_tool_server_mapping(servers)

        current_tool_ids = {str(tool.id) for tool in tools}

        # Detect and delete tools that no longer exist
        deleted_ids = self._state_tracker.get_deleted_tools(current_tool_ids)
        for tool_id in deleted_ids:
            server_id = tool_to_server.get(tool_id)
            if server_id and await self._fam_client.delete_tool(tool_id, server_id):
                self._state_tracker.mark_deleted(tool_id)

        # Process current tools
        for tool in tools:
            tool_id = str(tool.id)
            server_id = tool_to_server.get(tool_id)

            if not server_id:
                # Tool not associated with any server, skip
                continue

            current_hash = self._state_tracker.compute_hash(tool)

            if self._state_tracker.is_new_tool(tool_id):
                # New tool - create in FAM
                if await self._fam_client.create_tool(tool, server_id):
                    self._state_tracker.mark_synced(tool_id, current_hash)

            elif self._state_tracker.has_changed(tool_id, current_hash):
                # Tool changed - update in FAM
                if await self._fam_client.update_tool(tool, server_id):
                    self._state_tracker.mark_synced(tool_id, current_hash)

    def _build_tool_server_mapping(self, servers: List[Any]) -> Dict[str, str]:
        """Build mapping from tool ID to server ID.

        Args:
            servers: List of Server ORM objects

        Returns:
            Dict mapping tool_id to server_id
        """
        tool_to_server = {}
        for server in servers:
            if hasattr(server, "tools") and server.tools:
                for tool in server.tools:
                    tool_to_server[str(tool.id)] = str(server.id)
        return tool_to_server

    def get_stats(self) -> Dict[str, int]:
        """Get synchronization statistics.

        Returns:
            Dict with sync statistics
        """
        return {"synced_tools": len(self._state_tracker._fam_tools), "cached_hashes": len(self._state_tracker._tool_cache)}


# Made with Bob
