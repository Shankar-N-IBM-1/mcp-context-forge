"""IBM API Connect Federated API Management Plugin for ContextForge.

This plugin integrates ContextForge with IBM API Connect Federated API Management (FAM),
enabling automated synchronization of MCP servers, tools, and runtime metadata with
IBM API Connect's centralized governance platform.

Features
--------
- **Automated Synchronization**: Real-time sync of MCP virtual servers and tools
- **Metrics Collection**: Periodic aggregation and reporting of runtime metrics
- **Health Monitoring**: Continuous heartbeat monitoring and failure detection
- **Flexible Authentication**: Support for Basic Auth and API Key authentication
- **TLS/SSL Support**: One-way and mutual TLS with certificate management
- **Circuit Breaker**: Built-in resilience pattern for fault tolerance
- **Comprehensive Logging**: Detailed audit trail of all operations

Quick Start
-----------
1. Install the plugin:

   .. code-block:: bash

       pip install contextforge-apiconnect-fam

2. Configure in plugins/config.yaml:

   .. code-block:: yaml

       plugins:
         - name: "APIConnectFAM"
           kind: "contextforge_apiconnect_fam.APIConnectFAMPlugin"
           config:
             fam_enabled: true
             fam_base_url: "https://fam.example.com"
             fam_runtime_id: "my-runtime"
             fam_auth_type: "apikey"
             fam_api_key: "your-key"
             fam_client_id: "your-client-id"

3. Enable plugins in .env:

   .. code-block:: bash

       PLUGINS_ENABLED=true
       PLUGINS_CONFIG_FILE=plugins/config.yaml

Examples
--------
Basic configuration with API Key authentication:

>>> from contextforge_apiconnect_fam import APIConnectFAMPlugin, APIConnectFAMConfig
>>> config = APIConnectFAMConfig(
...     fam_enabled=True,
...     fam_base_url="https://fam.example.com",
...     fam_runtime_id="my-runtime",
...     fam_auth_type="apikey",
...     fam_api_key="your-key",
...     fam_client_id="your-client-id"
... )

Configuration with all credentials in config:

>>> config = APIConnectFAMConfig(
...     fam_enabled=True,
...     fam_base_url="https://fam.example.com",
...     fam_runtime_id="my-runtime",
...     fam_auth_type="apikey",
...     fam_api_key="your-api-key",
...     fam_client_id="your-client-id"
... )

See Also
--------
- Documentation: https://github.com/IBM/mcp-context-forge/tree/main/docs
- Repository: https://github.com/IBM/mcp-context-forge
- Issues: https://github.com/IBM/mcp-context-forge/issues

Notes
-----
The plugin requires ContextForge >= 1.0.0 and cpex >= 0.1.0.
All configuration including credentials must be provided in plugins/config.yaml.

"""

from .apiconnect_fam import APIConnectFAMConfig, APIConnectFAMPlugin

__version__ = "1.0.0"
__author__ = "Shankar N"
__license__ = "Apache-2.0"
__all__ = [
    "APIConnectFAMPlugin",
    "APIConnectFAMConfig",
    "__version__",
]
