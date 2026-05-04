"""FAM Asset Catalog API Client.

This module provides a client for interacting with the FAM (Federated API Management)
Asset Catalog API v1. It handles MCP Server synchronization with proper data type
conversion and validation according to the OpenAPI specification.

Copyright 2025
SPDX-License-Identifier: Apache-2.0
"""

import hashlib
import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

import httpx
import logging

from .models import ReregistrationReport

logger = logging.getLogger(__name__)


class FAMRuntimePayload:
    """Builder for FAM Runtime payloads following API v2 spec.
    
    Builds runtime registration payloads for POST /api/assetcatalog/v2/runtimes.
    
    Runtime types:
    - WEBMETHODS_GATEWAY: webMethods API Gateway
    - APIGEE: Apigee API Gateway
    - KONG: Kong API Gateway
    - AWS_API_GATEWAY: AWS API Gateway
    - AZURE_API_MANAGEMENT: Azure API Management
    
    Deployment types:
    - ON_PREMISE: On-premise deployment
    - CLOUD: Cloud deployment
    - HYBRID: Hybrid deployment
    """
    
    # Runtime type enums
    TYPE_WEBMETHODS_GATEWAY = "WEBMETHODS_GATEWAY"
    TYPE_APIGEE = "APIGEE"
    TYPE_KONG = "KONG"
    TYPE_AWS_API_GATEWAY = "AWS_API_GATEWAY"
    TYPE_AZURE_API_MANAGEMENT = "AZURE_API_MANAGEMENT"
    
    # Deployment type enums
    DEPLOYMENT_ON_PREMISE = "ON_PREMISE"
    DEPLOYMENT_CLOUD = "CLOUD"
    DEPLOYMENT_HYBRID = "HYBRID"
    
    @staticmethod
    def build_payload(
        name: str,
        description: str,
        runtime_type: str = TYPE_WEBMETHODS_GATEWAY,
        deployment_type: str = DEPLOYMENT_ON_PREMISE,
        region: Optional[str] = None,
        location: Optional[str] = None,
        host: Optional[str] = None,
        tags: Optional[List[str]] = None,
        capacity_value: Optional[str] = None,
        capacity_unit: Optional[str] = None,
        heartbeat_interval: int = 6000,
        publish_assets: bool = True,
        sync_assets: bool = True,
        send_metrics: bool = True
    ) -> Dict[str, Any]:
        """Build runtime registration payload.
        
        Args:
            name: Runtime display name (required)
            description: Runtime description (required)
            runtime_type: Runtime type enum (default: WEBMETHODS_GATEWAY)
            deployment_type: Deployment type enum (default: ON_PREMISE)
            region: Region identifier (e.g., "us-east-1")
            location: Location description (e.g., "US East")
            host: Host identifier
            tags: List of tags for the runtime
            capacity_value: Capacity value (e.g., "50")
            capacity_unit: Capacity unit (e.g., "per minute")
            heartbeat_interval: Heartbeat sync interval in milliseconds (default: 6000)
            publish_assets: Whether to publish assets (default: True)
            sync_assets: Whether to sync assets (default: True)
            send_metrics: Whether to send metrics (default: True)
            
        Returns:
            Runtime registration payload dict
        """
        payload: Dict[str, Any] = {
            "name": name,
            "description": description,
            "type": runtime_type,
            "deploymentType": deployment_type,
            "heartBeatSynchInterval": heartbeat_interval,
            "publishAssets": publish_assets,
            "syncAssets": sync_assets,
            "sendMetrics": send_metrics,
            "icon": ""  # Empty icon as per sample
        }
        
        # Add optional fields
        if region:
            payload["region"] = region
        if location:
            payload["location"] = location
        if host:
            payload["host"] = host
        if tags:
            payload["tags"] = tags[:50]  # Limit to 50 tags
        
        # Add capacity if both value and unit are provided
        if capacity_value and capacity_unit:
            payload["capacity"] = {
                "value": capacity_value,
                "unit": capacity_unit
            }
        
        return payload


class FAMServerPayload:
    """Builder for FAM MCP Server payloads following OpenAPI spec.
    
    Ensures all data types and constraints match the Asset Catalog API v1 specification:
    - mcpServerId: string (pattern: ^[a-zA-Z0-9_:-]+$, 1-255 chars)
    - name: string (1-255 chars)
    - description: string (max 1000 chars)
    - status: AssetStatus enum (ACTIVE, INACTIVE, DEPRECATED)
    - capabilities: array of MCPCapability enum
    - tags: array of string (max 50 items)
    - url: string (format: uri) - optional
    """
    
    # OpenAPI spec enums
    ASSET_STATUS_ACTIVE = "ACTIVE"
    ASSET_STATUS_INACTIVE = "INACTIVE"
    ASSET_STATUS_DEPRECATED = "DEPRECATED"
    
    CAPABILITY_LOGGING = "LOGGING"
    CAPABILITY_COMPLETIONS = "COMPLETIONS"
    CAPABILITY_PROMPTS = "PROMPTS"
    CAPABILITY_RESOURCES = "RESOURCES"
    CAPABILITY_TOOLS = "TOOLS"
    
    @staticmethod
    def _truncate_string(value: Optional[str], max_length: int) -> str:
        """Truncate string to maximum length.
        
        Args:
            value: String value to truncate
            max_length: Maximum allowed length
            
        Returns:
            Truncated string
        """
        if not value:
            return ""
        return str(value)[:max_length]
    
    @staticmethod
    def _get_status(enabled: bool) -> str:
        """Map ContextForge enabled flag to FAM AssetStatus enum.
        
        Args:
            enabled: ContextForge server enabled flag
            
        Returns:
            AssetStatus enum value (ACTIVE or INACTIVE)
        """
        return FAMServerPayload.ASSET_STATUS_ACTIVE if enabled else FAMServerPayload.ASSET_STATUS_INACTIVE
    
    @staticmethod
    def _get_capabilities(server: Any) -> List[str]:
        """Detect server capabilities from associated items.
        
        Args:
            server: ContextForge Server ORM object
            
        Returns:
            List of MCPCapability enum values
        """
        capabilities = []
        
        if hasattr(server, 'tools') and server.tools and len(server.tools) > 0:
            capabilities.append(FAMServerPayload.CAPABILITY_TOOLS)
        
        if hasattr(server, 'resources') and server.resources and len(server.resources) > 0:
            capabilities.append(FAMServerPayload.CAPABILITY_RESOURCES)
        
        if hasattr(server, 'prompts') and server.prompts and len(server.prompts) > 0:
            capabilities.append(FAMServerPayload.CAPABILITY_PROMPTS)
        
        return capabilities
    
    @staticmethod
    def _get_tags(server: Any) -> List[str]:
        """Extract and validate tags from server.
        
        Args:
            server: ContextForge Server ORM object
            
        Returns:
            List of tag strings (max 50 items)
        """
        tags = []
        if hasattr(server, 'tags') and isinstance(server.tags, list):
            tags = server.tags[:50]  # Enforce maxItems: 50
        return tags
    
    @classmethod
    def build_create_payload(cls, server: Any) -> Dict[str, Any]:
        """Build MCPServerCreate payload for POST request.
        
        Required fields: mcpServerId, name
        Optional fields: description, url, status, capabilities, tags, owner
        
        Args:
            server: ContextForge Server ORM object
            
        Returns:
            Dictionary matching MCPServerCreate schema
        """
        payload: Dict[str, Any] = {
            "mcpServerId": cls._truncate_string(str(server.id), 255),
            "name": cls._truncate_string(server.name, 255),
        }
        
        # Optional fields
        description = cls._truncate_string(server.description, 1000)
        if description:
            payload["description"] = description
        
        payload["status"] = cls._get_status(server.enabled)
        
        capabilities = cls._get_capabilities(server)
        if capabilities:
            payload["capabilities"] = capabilities
        
        tags = cls._get_tags(server)
        if tags:
            payload["tags"] = tags
        
        return payload
    
    @classmethod
    def build_update_payload(cls, server: Any) -> Dict[str, Any]:
        """Build MCPServerUpdate payload for PUT request.
        
        All fields are optional in update schema.
        
        Args:
            server: ContextForge Server ORM object
            
        Returns:
            Dictionary matching MCPServerUpdate schema
        """
        payload: Dict[str, Any] = {}
        
        name = cls._truncate_string(server.name, 255)
        if name:
            payload["name"] = name
        
        description = cls._truncate_string(server.description, 1000)
        if description:
            payload["description"] = description
        
        payload["status"] = cls._get_status(server.enabled)
        
        capabilities = cls._get_capabilities(server)
        if capabilities:
            payload["capabilities"] = capabilities
        
        tags = cls._get_tags(server)
        if tags:
            payload["tags"] = tags
        
        return payload


class FAMAssetCatalogClient:
    """Client for FAM Asset Catalog API v1.
    
    Handles MCP Server lifecycle operations (create, update, delete) with
    proper error handling and logging.
    
    Attributes:
        base_url: FAM API base URL
        runtime_id: Runtime identifier for API requests
        http_client: Async HTTP client for API calls
    """
    
    def __init__(
        self,
        base_url: str,
        runtime_id: str,
        auth_token: str,
        timeout: int = 30
    ):
        """Initialize FAM client.
        
        Args:
            base_url: FAM API base URL (e.g., https://fam.example.com)
            runtime_id: Runtime identifier
            auth_token: Bearer token for authentication
            timeout: HTTP request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.runtime_id = runtime_id
        self._http_client = httpx.AsyncClient(
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {auth_token}",
                "Content-Type": "application/json"
            }
        )
        self._endpoint = f"{self.base_url}/api/assetcatalog/v1/runtimes/{self.runtime_id}/mcp-servers"
    
    async def close(self) -> None:
        """Close HTTP client and release resources."""
        if self._http_client:
            await self._http_client.aclose()
    
    async def register_runtime(
        self,
        name: str,
        description: str,
        runtime_type: str = FAMRuntimePayload.TYPE_WEBMETHODS_GATEWAY,
        deployment_type: str = FAMRuntimePayload.DEPLOYMENT_ON_PREMISE,
        region: Optional[str] = None,
        location: Optional[str] = None,
        host: Optional[str] = None,
        tags: Optional[List[str]] = None,
        capacity_value: Optional[str] = None,
        capacity_unit: Optional[str] = None,
        heartbeat_interval: int = 6000
    ) -> Optional[ReregistrationReport]:
        """Register or update runtime in FAM Asset Catalog API v2.
        
        POST /api/assetcatalog/v2/runtimes
        
        Args:
            name: Runtime display name
            description: Runtime description
            runtime_type: Runtime type (default: WEBMETHODS_GATEWAY)
            deployment_type: Deployment type (default: ON_PREMISE)
            region: Region identifier (e.g., "us-east-1")
            location: Location description (e.g., "US East")
            host: Host identifier
            tags: List of tags for the runtime
            capacity_value: Capacity value (e.g., "50")
            capacity_unit: Capacity unit (e.g., "per minute")
            heartbeat_interval: Heartbeat sync interval in milliseconds
            
        Returns:
            ReregistrationReport with runtime ID and last sync timestamps if successful, None otherwise
        """
        try:
            # Build runtime registration payload
            payload = FAMRuntimePayload.build_payload(
                name=name,
                description=description,
                runtime_type=runtime_type,
                deployment_type=deployment_type,
                region=region,
                location=location,
                host=host,
                tags=tags,
                capacity_value=capacity_value,
                capacity_unit=capacity_unit,
                heartbeat_interval=heartbeat_interval,
                publish_assets=True,
                sync_assets=True,
                send_metrics=True
            )
            
            # POST to API v2 runtime endpoint
            endpoint = f"{self.base_url}/api/assetcatalog/v2/runtimes"
            logger.info(f"Registering runtime '{name}' at {endpoint}")
            
            response = await self._http_client.post(endpoint, json=payload)
            response.raise_for_status()
            
            # Extract runtime ID and re-registration report from response
            response_data = response.json()
            runtime_id = response_data.get("id") or response_data.get("runtimeId")
            
            if not runtime_id:
                logger.warning(f"Runtime registered but no ID returned in response: {response_data}")
                return None
            
            # Parse re-registration report (timestamps of last sync operations)
            # These fields may be present if this is a re-registration
            report = ReregistrationReport(
                runtime_id=str(runtime_id),
                last_registration_time=response_data.get("lastRegistrationTime"),
                last_heartbeat_time=response_data.get("lastHeartbeatTime"),
                last_metrics_time=response_data.get("lastMetricsTime"),
                last_asset_sync_time=response_data.get("lastAssetSyncTime")
            )
            
            logger.info(
                f"Successfully registered runtime '{name}' with ID: {runtime_id}, "
                f"report: {report.model_dump()}"
            )
            return report
                
        except httpx.HTTPStatusError as e:
            logger.error(
                f"FAM API error registering runtime '{name}': "
                f"status={e.response.status_code}, body={e.response.text}"
            )
            return None
        except httpx.HTTPError as e:
            logger.error(f"HTTP error registering runtime '{name}': {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error registering runtime '{name}': {e}")
            return None
    
    async def send_heartbeat(self, runtime_id: str) -> bool:
        """Send heartbeat for runtime to FAM Asset Catalog API v2.
        
        POST /api/engine/v2/runtimes/heartbeat
        
        Args:
            runtime_id: Runtime ID to send heartbeat for
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Build heartbeat payload
            import time
            payload = {
                "created": int(time.time()),
                "runtimeId": runtime_id
            }
            
            # POST to API v2 heartbeat endpoint
            endpoint = f"{self.base_url}/api/engine/v2/runtimes/heartbeat"
            
            response = await self._http_client.post(endpoint, json=payload)
            response.raise_for_status()
            
            logger.debug(f"Heartbeat sent successfully for runtime {runtime_id}")
            return True
                
        except httpx.HTTPStatusError as e:
            logger.error(
                f"FAM API error sending heartbeat for runtime {runtime_id}: "
                f"status={e.response.status_code}, body={e.response.text}"
            )
            return False
        except httpx.HTTPError as e:
            logger.error(f"HTTP error sending heartbeat for runtime {runtime_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending heartbeat for runtime {runtime_id}: {e}")
            return False
    
    async def create_server(self, server: Any) -> bool:
        """Create MCP Server in FAM.
        
        POST /api/assetcatalog/v1/runtimes/{runtimeId}/mcp-servers
        
        Args:
            server: ContextForge Server ORM object
            
        Returns:
            True if successful, False otherwise
        """
        try:
            payload = FAMServerPayload.build_create_payload(server)
            response = await self._http_client.post(self._endpoint, json=payload)
            response.raise_for_status()
            
            logger.info(f"Created MCP Server {server.id} in FAM")
            return True
            
        except httpx.HTTPStatusError as e:
            logger.error(
                f"FAM API error creating server {server.id}: "
                f"status={e.response.status_code}, body={e.response.text}"
            )
            return False
        except httpx.HTTPError as e:
            logger.error(f"HTTP error creating server {server.id} in FAM: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error creating server {server.id} in FAM: {e}", exc_info=True)
            return False
    
    async def update_server(self, server: Any) -> bool:
        """Update MCP Server in FAM.
        
        PUT /api/assetcatalog/v1/runtimes/{runtimeId}/mcp-servers/{id}
        
        Args:
            server: ContextForge Server ORM object
            
        Returns:
            True if successful, False otherwise
        """
        try:
            url = f"{self._endpoint}/{server.id}"
            payload = FAMServerPayload.build_update_payload(server)
            response = await self._http_client.put(url, json=payload)
            response.raise_for_status()
            
            logger.info(f"Updated MCP Server {server.id} in FAM")
            return True
            
        except httpx.HTTPStatusError as e:
            logger.error(
                f"FAM API error updating server {server.id}: "
                f"status={e.response.status_code}, body={e.response.text}"
            )
            return False
        except httpx.HTTPError as e:
            logger.error(f"HTTP error updating server {server.id} in FAM: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error updating server {server.id} in FAM: {e}", exc_info=True)
            return False
    
    async def delete_server(self, server_id: str) -> bool:
        """Delete MCP Server from FAM.
        
        DELETE /api/assetcatalog/v1/runtimes/{runtimeId}/mcp-servers/{id}
        
        Args:
            server_id: Server identifier
            
        Returns:
            True if successful, False otherwise
        """
        try:
            url = f"{self._endpoint}/{server_id}"
            response = await self._http_client.delete(url)
            response.raise_for_status()
            
            logger.info(f"Deleted MCP Server {server_id} from FAM")
            return True
            
        except httpx.HTTPStatusError as e:
            # 404 is acceptable for delete (already deleted)
            if e.response.status_code == 404:
                logger.info(f"Server {server_id} not found in FAM (already deleted)")
                return True
            
            logger.error(
                f"FAM API error deleting server {server_id}: "
                f"status={e.response.status_code}, body={e.response.text}"
            )
            return False
        except httpx.HTTPError as e:
            logger.error(f"HTTP error deleting server {server_id} from FAM: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error deleting server {server_id} from FAM: {e}", exc_info=True)
            return False


    
    async def create_tool(self, tool: Any, server_id: str) -> bool:
        """Create MCP Tool in FAM.
        
        POST /api/assetcatalog/v1/runtimes/{runtimeId}/mcp-servers/{mcpServerId}/mcp-tools
        
        Args:
            tool: ContextForge Tool ORM object
            server_id: Parent MCP Server ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            url = f"{self._endpoint}/{server_id}/mcp-tools"
            payload = FAMToolPayload.build_create_payload(tool, server_id)
            response = await self._http_client.post(url, json=payload)
            response.raise_for_status()
            
            logger.info(f"Created MCP Tool {tool.id} in FAM (server: {server_id})")
            return True
            
        except httpx.HTTPStatusError as e:
            logger.error(
                f"FAM API error creating tool {tool.id}: "
                f"status={e.response.status_code}, body={e.response.text}"
            )
            return False
        except httpx.HTTPError as e:
            logger.error(f"HTTP error creating tool {tool.id} in FAM: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error creating tool {tool.id} in FAM: {e}", exc_info=True)
            return False
    
    async def update_tool(self, tool: Any, server_id: str) -> bool:
        """Update MCP Tool in FAM.
        
        PUT /api/assetcatalog/v1/runtimes/{runtimeId}/mcp-servers/{mcpServerId}/mcp-tools/{id}
        
        Args:
            tool: ContextForge Tool ORM object
            server_id: Parent MCP Server ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            url = f"{self._endpoint}/{server_id}/mcp-tools/{tool.id}"
            payload = FAMToolPayload.build_update_payload(tool)
            response = await self._http_client.put(url, json=payload)
            response.raise_for_status()
            
            logger.info(f"Updated MCP Tool {tool.id} in FAM (server: {server_id})")
            return True
            
        except httpx.HTTPStatusError as e:
            logger.error(
                f"FAM API error updating tool {tool.id}: "
                f"status={e.response.status_code}, body={e.response.text}"
            )
            return False
        except httpx.HTTPError as e:
            logger.error(f"HTTP error updating tool {tool.id} in FAM: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error updating tool {tool.id} in FAM: {e}", exc_info=True)
            return False
    
    async def delete_tool(self, tool_id: str, server_id: str) -> bool:
        """Delete MCP Tool from FAM.
        
        DELETE /api/assetcatalog/v1/runtimes/{runtimeId}/mcp-servers/{mcpServerId}/mcp-tools/{id}
        
        Args:
            tool_id: Tool identifier
            server_id: Parent MCP Server ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            url = f"{self._endpoint}/{server_id}/mcp-tools/{tool_id}"
            response = await self._http_client.delete(url)
            response.raise_for_status()
            
            logger.info(f"Deleted MCP Tool {tool_id} from FAM (server: {server_id})")
            return True
            
        except httpx.HTTPStatusError as e:
            # 404 is acceptable for delete (already deleted)
            if e.response.status_code == 404:
                logger.info(f"Tool {tool_id} not found in FAM (already deleted)")
                return True
            
            logger.error(
                f"FAM API error deleting tool {tool_id}: "
                f"status={e.response.status_code}, body={e.response.text}"
            )
            return False
        except httpx.HTTPError as e:
            logger.error(f"HTTP error deleting tool {tool_id} from FAM: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error deleting tool {tool_id} from FAM: {e}", exc_info=True)
    
    async def submit_metrics(self, metrics_payload: Dict[str, Any]) -> bool:
        """Submit metrics to FAM.
        
        POST /api/engine/v3/runtimes/{runtimeId}/metrics
        
        Args:
            metrics_payload: AgentMetricsModel payload dict
            
        Returns:
            True if successful (202 Accepted), False otherwise
        """
        try:
            # Use engine v3 endpoint for metrics
            metrics_url = f"{self.base_url}/api/engine/v3/runtimes/{self.runtime_id}/metrics"
            response = await self._http_client.post(metrics_url, json=metrics_payload)
            response.raise_for_status()
            
            # Metrics endpoint returns 202 Accepted
            if response.status_code == 202:
                logger.info(f"Successfully submitted metrics to FAM for runtime {self.runtime_id}")
                return True
            else:
                logger.warning(
                    f"Unexpected status code {response.status_code} when submitting metrics"
                )
                return False
                
        except httpx.HTTPStatusError as e:
            logger.error(
                f"FAM API error submitting metrics: "
                f"status={e.response.status_code}, body={e.response.text}"
            )
            return False
        except httpx.HTTPError as e:
            logger.error(f"HTTP error submitting metrics to FAM: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error submitting metrics to FAM: {e}", exc_info=True)
            return False


class FAMToolPayload:
    """Builder for FAM MCP Tool payloads following OpenAPI spec.
    
    Ensures all data types and constraints match the Asset Catalog API v1 specification:
    - mcpServerId: string (parent server identifier)
    - mcpToolId: string (pattern: ^[a-zA-Z0-9_:-]+$) - optional
    - name: string (1-255 chars) - required
    - description: string (max 1000 chars)
    - requestType: MCPToolRequestType enum (HTTP, SSE)
    - inputSchema: MCPToolSchema object - required
    - outputSchema: MCPToolSchema object - optional
    - annotations: MCPToolAnnotations object - optional
    - tags: array of string (max 50 items)
    """
    
    # OpenAPI spec enums
    REQUEST_TYPE_HTTP = "HTTP"
    REQUEST_TYPE_SSE = "SSE"
    
    @staticmethod
    def _truncate_string(value: Optional[str], max_length: int) -> str:
        """Truncate string to maximum length.
        
        Args:
            value: String value to truncate
            max_length: Maximum allowed length
            
        Returns:
            Truncated string
        """
        if not value:
            return ""
        return str(value)[:max_length]
    
    @staticmethod
    def _get_request_type(tool: Any) -> str:
        """Map ContextForge request_type to FAM MCPToolRequestType enum.
        
        Args:
            tool: ContextForge Tool ORM object
            
        Returns:
            MCPToolRequestType enum value (HTTP or SSE)
        """
        # ContextForge uses "SSE" or "HTTP" - map directly
        request_type = getattr(tool, 'request_type', 'SSE')
        if request_type and request_type.upper() in ['HTTP', 'SSE']:
            return request_type.upper()
        return FAMToolPayload.REQUEST_TYPE_SSE  # Default to SSE
    
    @staticmethod
    def _get_tags(tool: Any) -> List[str]:
        """Extract and validate tags from tool.
        
        Args:
            tool: ContextForge Tool ORM object
            
        Returns:
            List of tag strings (max 50 items)
        """
        tags = []
        if hasattr(tool, 'tags') and isinstance(tool.tags, list):
            tags = tool.tags[:50]  # Enforce maxItems: 50
        return tags
    
    @staticmethod
    def _build_schema(schema_dict: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Build MCPToolSchema from ContextForge schema.
        
        Args:
            schema_dict: ContextForge schema dictionary
            
        Returns:
            MCPToolSchema compliant dictionary or None
        """
        if not schema_dict or not isinstance(schema_dict, dict):
            return None
        
        # Ensure required 'type' field exists
        if 'type' not in schema_dict:
            schema_dict['type'] = 'object'
        
        return schema_dict
    
    @staticmethod
    def _build_annotations(tool: Any) -> Optional[Dict[str, Any]]:
        """Build MCPToolAnnotations from ContextForge tool.
        
        Args:
            tool: ContextForge Tool ORM object
            
        Returns:
            MCPToolAnnotations compliant dictionary or None
        """
        if not hasattr(tool, 'annotations') or not tool.annotations:
            return None
        
        annotations = {}
        tool_annotations = tool.annotations
        
        # Map known annotation fields
        if 'title' in tool_annotations:
            annotations['title'] = str(tool_annotations['title'])
        if 'readOnlyHint' in tool_annotations:
            annotations['readOnlyHint'] = bool(tool_annotations['readOnlyHint'])
        if 'destructiveHint' in tool_annotations:
            annotations['destructiveHint'] = bool(tool_annotations['destructiveHint'])
        if 'idempotentHint' in tool_annotations:
            annotations['idempotentHint'] = bool(tool_annotations['idempotentHint'])
        if 'openWorldHint' in tool_annotations:
            annotations['openWorldHint'] = bool(tool_annotations['openWorldHint'])
        
        return annotations if annotations else None
    
    @classmethod
    def build_create_payload(cls, tool: Any, server_id: str) -> Dict[str, Any]:
        """Build MCPToolCreate payload for POST request.
        
        Required fields: mcpServerId, name, inputSchema
        Optional fields: mcpToolId, description, requestType, outputSchema, annotations, tags, owner
        
        Args:
            tool: ContextForge Tool ORM object
            server_id: Parent MCP Server ID
            
        Returns:
            Dictionary matching MCPToolCreate schema
        """
        # Build input schema (required)
        input_schema = cls._build_schema(tool.input_schema)
        if not input_schema:
            # Provide minimal valid schema if missing
            input_schema = {"type": "object"}
        
        payload: Dict[str, Any] = {
            "mcpServerId": cls._truncate_string(server_id, 255),
            "name": cls._truncate_string(tool.original_name or tool.custom_name, 255),
            "inputSchema": input_schema,
        }
        
        # Optional mcpToolId
        if hasattr(tool, 'id') and tool.id:
            payload["mcpToolId"] = cls._truncate_string(str(tool.id), 255)
        
        # Optional description
        description = cls._truncate_string(tool.description or tool.original_description, 1000)
        if description:
            payload["description"] = description
        
        # Optional requestType
        payload["requestType"] = cls._get_request_type(tool)
        
        # Optional outputSchema
        output_schema = cls._build_schema(tool.output_schema)
        if output_schema:
            payload["outputSchema"] = output_schema
        
        # Optional annotations
        annotations = cls._build_annotations(tool)
        if annotations:
            payload["annotations"] = annotations
        
        # Optional tags
        tags = cls._get_tags(tool)
        if tags:
            payload["tags"] = tags
        
        return payload
    
    @classmethod
    def build_update_payload(cls, tool: Any) -> Dict[str, Any]:
        """Build MCPToolUpdate payload for PUT request.
        
        All fields are optional in update schema.
        
        Args:
            tool: ContextForge Tool ORM object
            
        Returns:
            Dictionary matching MCPToolUpdate schema
        """
        payload: Dict[str, Any] = {}
        
        # Optional name
        name = cls._truncate_string(tool.original_name or tool.custom_name, 255)
        if name:
            payload["name"] = name
        
        # Optional description
        description = cls._truncate_string(tool.description or tool.original_description, 1000)
        if description:
            payload["description"] = description
        
        # Optional requestType
        payload["requestType"] = cls._get_request_type(tool)
        
        # Optional inputSchema
        input_schema = cls._build_schema(tool.input_schema)
        if input_schema:
            payload["inputSchema"] = input_schema
        
        # Optional outputSchema
        output_schema = cls._build_schema(tool.output_schema)
        if output_schema:
            payload["outputSchema"] = output_schema
        
        # Optional annotations
        annotations = cls._build_annotations(tool)
        if annotations:
            payload["annotations"] = annotations
        
        # Optional tags
        tags = cls._get_tags(tool)
        if tags:
            payload["tags"] = tags
        
        return payload


class ToolStateTracker:
    """Tracks tool state for change detection.
    
    Uses content hashing to detect when tools have changed and need
    to be synced to FAM.
    
    Attributes:
        _tool_cache: Maps tool_id to content hash
        _fam_tools: Set of tool IDs that exist in FAM
    """
    
    def __init__(self):
        """Initialize state tracker."""
        self._tool_cache: Dict[str, str] = {}
        self._fam_tools: Set[str] = set()
    
    @staticmethod
    def compute_hash(tool: Any) -> str:
        """Compute SHA-256 hash of tool content.
        
        Includes: name, description, enabled, tags, input_schema, output_schema
        
        Args:
            tool: ContextForge Tool ORM object
            
        Returns:
            SHA-256 hash string
        """
        tool_data = {
            "name": tool.original_name or tool.custom_name,
            "description": tool.description or tool.original_description,
            "enabled": tool.enabled,
            "tags": sorted(tool.tags) if tool.tags else [],
            "request_type": tool.request_type,
            "input_schema": json.dumps(tool.input_schema, sort_keys=True) if tool.input_schema else "",
            "output_schema": json.dumps(tool.output_schema, sort_keys=True) if tool.output_schema else "",
        }
        data_str = json.dumps(tool_data, sort_keys=True)
        return hashlib.sha256(data_str.encode()).hexdigest()
    
    def is_new_tool(self, tool_id: str) -> bool:
        """Check if tool is new (not in FAM).
        
        Args:
            tool_id: Tool identifier
            
        Returns:
            True if tool is new
        """
        return tool_id not in self._fam_tools
    
    def has_changed(self, tool_id: str, current_hash: str) -> bool:
        """Check if tool content has changed.
        
        Args:
            tool_id: Tool identifier
            current_hash: Current content hash
            
        Returns:
            True if tool has changed
        """
        cached_hash = self._tool_cache.get(tool_id)
        return cached_hash != current_hash
    
    def mark_synced(self, tool_id: str, content_hash: str) -> None:
        """Mark tool as synced to FAM.
        
        Args:
            tool_id: Tool identifier
            content_hash: Content hash of synced state
        """
        self._fam_tools.add(tool_id)
        self._tool_cache[tool_id] = content_hash
    
    def mark_deleted(self, tool_id: str) -> None:
        """Mark tool as deleted from FAM.
        
        Args:
            tool_id: Tool identifier
        """
        self._fam_tools.discard(tool_id)
        self._tool_cache.pop(tool_id, None)
    
    def get_deleted_tools(self, current_tool_ids: Set[str]) -> Set[str]:
        """Get tools that exist in FAM but not in current DB.
        
        Args:
            current_tool_ids: Set of current tool IDs from database
            
        Returns:
            Set of tool IDs that were deleted
        """
        return self._fam_tools - current_tool_ids

class FAMMetricsPayload:
    """Builder for FAM metrics payloads following OpenAPI spec.
    
    Builds AgentMetricsModel payload structure:
    - timestamp: epoch milliseconds
    - runtimeTransactionMetrics: runtime-level aggregated metrics
    - mcpServerTransactionMetricsList: list of server metrics with nested tool metrics
    - mcpServersTransactionMetricsSummary: pre-computed summary (optional)
    """
    
    @staticmethod
    def _convert_to_milliseconds(dt: datetime) -> int:
        """Convert datetime to epoch milliseconds.
        
        Args:
            dt: Datetime object
            
        Returns:
            Epoch milliseconds as integer
        """
        return int(dt.timestamp() * 1000)
    
    @staticmethod
    def _aggregate_metrics(metrics: List[Any]) -> Dict[str, Any]:
        """Aggregate raw metrics into API metrics format.
        
        Args:
            metrics: List of metric objects (ToolMetric or ServerMetric)
            
        Returns:
            Dict with transactionCount, averageLatency, averageResponseTime
        """
        if not metrics:
            return {
                "transactionCount": 0,
                "averageLatency": 0.0,
                "averageResponseTime": 0.0,
                "averageBackendResponseTime": 0.0
            }
        
        total_count = len(metrics)
        # Convert response_time from seconds to milliseconds
        response_times_ms = [m.response_time * 1000 for m in metrics]
        avg_response_time = sum(response_times_ms) / total_count if total_count > 0 else 0.0
        
        return {
            "transactionCount": total_count,
            "averageLatency": avg_response_time,  # Using response time as latency
            "averageResponseTime": avg_response_time,
            "averageBackendResponseTime": avg_response_time * 0.8  # Estimate backend time as 80% of total
        }
    
    @staticmethod
    def _aggregate_metrics_by_status(metrics: List[Any]) -> Dict[str, Dict[str, Any]]:
        """Aggregate metrics grouped by HTTP status code ranges.
        
        Args:
            metrics: List of metric objects
            
        Returns:
            Dict with keys "2xx", "4xx", "5xx" containing aggregated metrics
        """
        # Group metrics by success/failure (map to 2xx/5xx)
        success_metrics = [m for m in metrics if m.is_success]
        failure_metrics = [m for m in metrics if not m.is_success]
        
        result = {}
        
        if success_metrics:
            result["2xx"] = FAMMetricsPayload._aggregate_metrics(success_metrics)
        
        if failure_metrics:
            result["5xx"] = FAMMetricsPayload._aggregate_metrics(failure_metrics)
        
        return result
    
    @staticmethod
    def build_tool_metrics(tool_id: str, tool_metrics: List[Any]) -> Dict[str, Any]:
        """Build MCPToolTransactionMetrics payload.
        
        Args:
            tool_id: Tool identifier
            tool_metrics: List of ToolMetric objects
            
        Returns:
            MCPToolTransactionMetrics dict
        """
        return {
            "toolId": tool_id,
            "apiMetrics": FAMMetricsPayload._aggregate_metrics(tool_metrics),
            "metricsByStatusCode": FAMMetricsPayload._aggregate_metrics_by_status(tool_metrics)
        }
    
    @staticmethod
    def build_server_metrics(
        server_id: str,
        server_metrics: List[Any],
        tool_metrics_map: Dict[str, List[Any]]
    ) -> Dict[str, Any]:
        """Build MCPServerTransactionMetrics payload.
        
        Args:
            server_id: Server identifier
            server_metrics: List of ServerMetric objects
            tool_metrics_map: Dict mapping tool_id to list of ToolMetric objects
            
        Returns:
            MCPServerTransactionMetrics dict
        """
        # Build tool metrics list
        tool_metrics_list = []
        for tool_id, metrics in tool_metrics_map.items():
            if metrics:
                tool_metrics_list.append(
                    FAMMetricsPayload.build_tool_metrics(tool_id, metrics)
                )
        
        return {
            "serverId": server_id,
            "apiMetrics": FAMMetricsPayload._aggregate_metrics(server_metrics),
            "metricsByStatusCode": FAMMetricsPayload._aggregate_metrics_by_status(server_metrics),
            "mcpToolTransactionMetricsList": tool_metrics_list
        }
    
    @staticmethod
    def build_runtime_metrics(all_metrics: List[Any]) -> Dict[str, Any]:
        """Build RuntimeTransactionMetrics payload.
        
        Args:
            all_metrics: Combined list of all ServerMetric and ToolMetric objects
            
        Returns:
            RuntimeTransactionMetrics dict
        """
        return {
            "apiMetrics": FAMMetricsPayload._aggregate_metrics(all_metrics),
            "metricsByStatusCode": FAMMetricsPayload._aggregate_metrics_by_status(all_metrics)
        }
    
    @staticmethod
    def build_payload(
        timestamp: datetime,
        server_metrics_map: Dict[str, List[Any]],
        tool_metrics_by_server: Dict[str, Dict[str, List[Any]]]
    ) -> Dict[str, Any]:
        """Build complete AgentMetricsModel payload.
        
        Args:
            timestamp: Timestamp for the metrics collection
            server_metrics_map: Dict mapping server_id to list of ServerMetric objects
            tool_metrics_by_server: Dict mapping server_id to dict of tool_id to ToolMetric list
            
        Returns:
            Complete AgentMetricsModel payload dict
        """
        # Build server metrics list
        mcp_server_metrics_list = []
        all_metrics = []
        
        for server_id, server_metrics in server_metrics_map.items():
            tool_metrics_map = tool_metrics_by_server.get(server_id, {})
            
            # Add to combined metrics for runtime summary
            all_metrics.extend(server_metrics)
            for tool_metrics in tool_metrics_map.values():
                all_metrics.extend(tool_metrics)
            
            # Build server metrics entry
            if server_metrics or tool_metrics_map:
                mcp_server_metrics_list.append(
                    FAMMetricsPayload.build_server_metrics(
                        server_id,
                        server_metrics,
                        tool_metrics_map
                    )
                )
        
        # Build runtime metrics
        runtime_metrics = FAMMetricsPayload.build_runtime_metrics(all_metrics)
        
        # Build summary metrics
        summary_metrics = FAMMetricsPayload._aggregate_metrics(all_metrics)
        
        return {
            "timestamp": FAMMetricsPayload._convert_to_milliseconds(timestamp),
            "runtimeTransactionMetrics": runtime_metrics,
            "mcpServerTransactionMetricsList": mcp_server_metrics_list,
            "mcpServersTransactionMetricsSummary": summary_metrics
        }


class ServerStateTracker:
    """Tracks server synchronization state with FAM.

    
    Uses content hashing to detect when servers have changed and need
    to be synced to FAM.
    
    Attributes:
        _server_cache: Maps server_id to content hash
        _fam_servers: Set of server IDs that exist in FAM
    """
    
    def __init__(self):
        """Initialize state tracker."""
        self._server_cache: Dict[str, str] = {}
        self._fam_servers: Set[str] = set()
    
    @staticmethod
    def compute_hash(server: Any) -> str:
        """Compute SHA-256 hash of server content.
        
        Includes: name, description, enabled, tags, tool/resource/prompt counts
        
        Args:
            server: ContextForge Server ORM object
            
        Returns:
            SHA-256 hash string
        """
        server_data = {
            "name": server.name,
            "description": server.description,
            "enabled": server.enabled,
            "tags": sorted(server.tags) if server.tags else [],
            "tool_count": len(server.tools) if server.tools else 0,
            "resource_count": len(server.resources) if server.resources else 0,
            "prompt_count": len(server.prompts) if server.prompts else 0,
        }
        data_str = json.dumps(server_data, sort_keys=True)
        return hashlib.sha256(data_str.encode()).hexdigest()
    
    def is_new_server(self, server_id: str) -> bool:
        """Check if server is new (not in FAM).
        
        Args:
            server_id: Server identifier
            
        Returns:
            True if server is new
        """
        return server_id not in self._fam_servers
    
    def has_changed(self, server_id: str, current_hash: str) -> bool:
        """Check if server content has changed.
        
        Args:
            server_id: Server identifier
            current_hash: Current content hash
            
        Returns:
            True if server has changed
        """
        cached_hash = self._server_cache.get(server_id)
        return cached_hash != current_hash
    
    def mark_synced(self, server_id: str, content_hash: str) -> None:
        """Mark server as synced to FAM.
        
        Args:
            server_id: Server identifier
            content_hash: Content hash of synced state
        """
        self._fam_servers.add(server_id)
        self._server_cache[server_id] = content_hash
    
    def mark_deleted(self, server_id: str) -> None:
        """Mark server as deleted from FAM.
        
        Args:
            server_id: Server identifier
        """
        self._fam_servers.discard(server_id)
        self._server_cache.pop(server_id, None)
    
    def get_deleted_servers(self, current_server_ids: Set[str]) -> Set[str]:
        """Get servers that exist in FAM but not in current DB.
        
        Args:
            current_server_ids: Set of current server IDs from database
            
        Returns:
            Set of server IDs that were deleted
        """
        return self._fam_servers - current_server_ids

# Made with Bob
