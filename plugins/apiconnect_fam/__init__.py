"""IBM API Connect Federated API Management Plugin for ContextForge.

This plugin integrates ContextForge with IBM API Connect Federated API Management (FAM),
enabling automated synchronization of MCP servers, tools, and runtime metadata with
IBM API Connect's centralized governance platform.

The plugin provides:
    - Automatic runtime registration with FAM
    - Periodic heartbeat to maintain connection status
    - Server and tool synchronization with change detection
    - Metrics collection and reporting
    - Circuit breaker pattern for fault tolerance
    - Retry logic with exponential backoff

Key Components:
    - APIConnectFAMPlugin: Main plugin class that orchestrates all operations
    - APIConnectFAMConfig: Configuration model with validation
    - ActivityOrchestrator: Manages scheduled activities
    - FAMAssetCatalogClient: HTTP client for FAM API communication

Requirements:
    - ContextForge >= 1.0.0
    - cpex >= 0.1.0
    - Python >= 3.8

Configuration:
    All configuration including credentials must be provided in plugins/config.yaml.
    See APIConnectFAMConfig for available configuration options.

Example:
    Basic plugin configuration in plugins/config.yaml:
    
    ```yaml
    plugins:
      - name: apiconnect_fam
        enabled: true
        config:
          fam_enabled: true
          fam_base_url: "https://fam.example.com"
          fam_runtime_id: "my-runtime-id"
          fam_auth_type: "basic"
          fam_username: "admin"
          fam_password: "secret"
    ```

Notes:
    - The plugin uses circuit breaker pattern to prevent cascading failures
    - All API calls include retry logic with exponential backoff
    - State tracking ensures efficient synchronization (only changed items are synced)
    - TLS/SSL configuration supports both one-way and mutual TLS

"""

from .apiconnect_fam import APIConnectFAMConfig, APIConnectFAMPlugin

__version__ = "0.1.0"
__author__ = "Shankar N"
__license__ = "Apache-2.0"
__all__ = [
    "APIConnectFAMPlugin",
    "APIConnectFAMConfig",
    "__version__",
]
