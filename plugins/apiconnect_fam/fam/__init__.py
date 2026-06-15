"""Location: ./plugins/apiconnect_fam/fam/__init__.py
Copyright 2026
SPDX-License-Identifier: Apache-2.0
Authors: Shankar N

FAM Client Module.

This module provides a comprehensive interface to IBM API Connect
Federated API Management (FAM) Asset Catalog and Engine APIs.

The module is organized into:
    - Client: HTTP client with authentication and circuit breaker
    - Endpoints: API endpoint constants
    - Payloads: Request/response payload builders

Components:
    - FAMAssetCatalogClient: Main HTTP client for FAM API operations
    - FAMEndpoints: Constants for all FAM API endpoints
    - FAMMetricsPayload: Builder for metrics payloads
    - FAMRuntimePayload: Builder for runtime registration payloads
    - FAMServerPayload: Builder for server payloads
    - FAMToolPayload: Builder for tool payloads

Features:
    - Automatic authentication (Basic Auth or API Key)
    - Circuit breaker pattern for fault tolerance
    - Retry logic with exponential backoff
    - TLS/SSL support (one-way and mutual TLS)
    - Comprehensive error handling and logging

Example:
    ```python
    # Create FAM client
    client = FAMAssetCatalogClient(
        base_url="https://fam.example.com",
        runtime_id="my-runtime",
        auth_type="basic",
        username="admin",
        password="secret"
    )
    
    # Register runtime
    report = await client.register_runtime(
        name="My Runtime",
        description="Production runtime",
        runtime_type="MCP_CONTEXT_FORGE"
    )
    
    # Create server
    success = await client.create_server(server_obj)
    
    # Close client
    await client.close()
    ```

API Versions:
    - Asset Catalog API v1: Servers and tools management
    - Asset Catalog API v2: Runtime registration
    - Engine API v2: Heartbeat
    - Engine API v3: Metrics

Notes:
    - All API calls are asynchronous
    - Circuit breaker protects against cascading failures
    - Payload builders ensure API compliance
"""

# Export main client
from .client import FAMAssetCatalogClient

# Export endpoints
from .endpoints import FAMEndpoints

# Export payload builders
from .payloads import (
    FAMMetricsPayload,
    FAMRuntimePayload,
    FAMServerPayload,
    FAMToolPayload,
)

__all__ = [
    # Client
    "FAMAssetCatalogClient",
    # Endpoints
    "FAMEndpoints",
    # Payload Builders
    "FAMMetricsPayload",
    "FAMRuntimePayload",
    "FAMServerPayload",
    "FAMToolPayload",
]
