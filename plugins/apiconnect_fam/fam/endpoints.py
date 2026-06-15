"""Location: ./plugins/apiconnect_fam/fam/endpoints.py
Copyright 2026
SPDX-License-Identifier: Apache-2.0
Authors: Shankar N

IBM API Connect Federated API Management API Endpoint Constants.

This module defines all FAM API endpoint URL patterns as constants.
Endpoints are organized by API version and functional area.

API Structure:
    - Ingress API v1: Authentication and token management
    - Asset Catalog API v1: Server and tool management
    - Asset Catalog API v2: Runtime registration and types
    - Engine API v2: Heartbeat operations
    - Engine API v3: Metrics submission

Endpoint Categories:
    - Authentication: Token generation for API key auth
    - Runtimes: Runtime registration and type management
    - Servers: MCP server CRUD operations
    - Tools: MCP tool CRUD and bulk operations
    - Heartbeat: Runtime status updates
    - Metrics: Performance metrics submission

Usage:
    ```python
    # Format endpoint with runtime_id
    endpoint = FAMEndpoints.SERVERS_BASE.format(runtime_id="my-runtime")
    # Result: "/api/assetcatalog/v1/runtimes/my-runtime/mcp-servers"
    
    # Format endpoint with multiple parameters
    endpoint = FAMEndpoints.TOOL_BY_ID.format(
        runtime_id="my-runtime",
        server_id="server-1",
        tool_id="tool-1"
    )
    ```

Notes:
    - All endpoints are relative paths (no base URL)
    - Use .format() to substitute runtime_id, server_id, tool_id
    - Endpoints follow RESTful conventions
    - Bulk operations use POST with action suffix (e.g., /bulk/create)
"""


class FAMEndpoints:
    """IBM API Connect Federated API Management Asset Catalog and Engine API endpoint constants."""

    # Ingress API v1 - Authentication
    TOKEN = "/api/ingress/v1/token"

    # Asset Catalog API v1 - Servers
    SERVERS_BASE = "/api/assetcatalog/v1/runtimes/{runtime_id}/mcp-servers"
    SERVER_BY_ID = "/api/assetcatalog/v1/runtimes/{runtime_id}/mcp-servers/{server_id}"

    # Asset Catalog API v1 - Tools
    TOOLS_BASE = "/api/assetcatalog/v1/runtimes/{runtime_id}/mcp-servers/{server_id}/mcp-tools"
    TOOL_BY_ID = "/api/assetcatalog/v1/runtimes/{runtime_id}/mcp-servers/{server_id}/mcp-tools/{tool_id}"
    TOOLS_BULK_CREATE = "/api/assetcatalog/v1/runtimes/{runtime_id}/mcp-servers/{server_id}/mcp-tools/bulk/create"
    TOOLS_BULK_UPDATE = "/api/assetcatalog/v1/runtimes/{runtime_id}/mcp-servers/{server_id}/mcp-tools/bulk/update"
    TOOLS_BULK_DELETE = "/api/assetcatalog/v1/runtimes/{runtime_id}/mcp-servers/{server_id}/mcp-tools/bulk/delete"

    # Asset Catalog API v2 - Runtimes
    RUNTIMES = "/api/assetcatalog/v2/runtimes"
    RUNTIME_TYPES = "/api/assetcatalog/v2/runtimes/types"

    # Engine API v2 - Heartbeat
    HEARTBEAT = "/api/engine/v2/runtimes/heartbeat"

    # Engine API v3 - Metrics
    METRICS = "/api/engine/v3/runtimes/{runtime_id}/metrics"
