"""FAM Client Module.

This module provides a modular interface to the FAM (Federated API Management)
Asset Catalog and Engine APIs.

Copyright 2025
SPDX-License-Identifier: Apache-2.0
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

# Made with Bob
