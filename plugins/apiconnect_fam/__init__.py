"""IBM API Connect Federated API Management Plugin for ContextForge.

This plugin integrates ContextForge with IBM API Connect Federated API Management (FAM),
enabling automated synchronization of MCP servers, tools, and runtime metadata with
IBM API Connect's centralized governance platform.


Notes
-----
The plugin requires ContextForge >= 1.0.0 and cpex >= 0.1.0.
All configuration including credentials must be provided in plugins/config.yaml.

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
