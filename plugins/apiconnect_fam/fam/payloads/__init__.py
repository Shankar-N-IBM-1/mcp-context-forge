"""Location: ./plugins/apiconnect_fam/fam/payloads/__init__.py
Copyright 2026
SPDX-License-Identifier: Apache-2.0
Authors: Shankar N

FAM Payload Builders.

This package provides builder classes for constructing FAM API request payloads.
Each builder ensures compliance with the FAM OpenAPI specification, including
data types, constraints, and required fields.

Payload Builders:
    - FAMMetricsPayload: Builds metrics payloads (AgentMetricsModel)
    - FAMRuntimePayload: Builds runtime registration payloads
    - FAMServerPayload: Builds MCP server payloads (create/update)
    - FAMToolPayload: Builds MCP tool payloads (create/update)

Features:
    - Automatic field validation and truncation
    - Schema normalization for tools
    - Tag sanitization (whitespace removal, length limits)
    - Capability detection from relationships
    - Safe string sanitization for FAM API compliance

Example:
    ```python
    # Build server payload
    server_payload = FAMServerPayload.build_create_payload(server_obj)
    
    # Build tool payload
    tool_payload = FAMToolPayload.build_create_payload(tool_obj, server_id)
    
    # Build metrics payload
    metrics_payload = FAMMetricsPayload.build_payload(
        timestamp=datetime.now(),
        server_metrics_map=server_metrics,
        tool_metrics_by_server=tool_metrics
    )
    
    # Build runtime payload
    runtime_payload = FAMRuntimePayload.build_payload(
        runtime_id="my-runtime",
        name="My Runtime",
        description="Production runtime",
        runtime_type="MCP_CONTEXT_FORGE"
    )
    ```

Notes:
    - All builders are static classes (no instantiation needed)
    - Payloads match FAM OpenAPI specification exactly
    - Field truncation prevents API validation errors
    - Schema builders handle nested structures recursively
"""

from .metrics import FAMMetricsPayload
from .runtime import FAMRuntimePayload
from .server import FAMServerPayload
from .tool import FAMToolPayload

__all__ = [
    "FAMMetricsPayload",
    "FAMRuntimePayload",
    "FAMServerPayload",
    "FAMToolPayload",
]
