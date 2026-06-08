"""Location: ./plugins/apiconnect_fam/fam/payloads/tool.py
Copyright 2025
SPDX-License-Identifier: Apache-2.0
Authors: Shankar N

FAM Tool Payload Builder.
"""

# Standard
from typing import Any, Dict, List, Optional


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
    def _sanitize_safe_string(value: Optional[str]) -> str:
        """Sanitize string to match FAM API safeString pattern.

        Pattern: ^[\\()_+@!#$%^&{}-=,.~'`\\p{L}\\p{M}\\p{N}\\p{So}\\p{Sc}\\p{Sk}\\s]*$

        Removes characters that don't match the FAM API pattern which allows:
        - Specific punctuation: backslash, parentheses, underscore, plus, at, exclamation,
          hash, dollar, percent, caret, ampersand, braces, hyphen, equals, comma,
          period, tilde, apostrophe, backtick
        - Unicode letters, marks, numbers, symbols, currency, modifiers
        - Whitespace

        Note: Colon (:) is NOT in the allowed character set per FAM API spec.
        Backticks are converted to single quotes for better readability.

        Args:
            value: String value to sanitize

        Returns:
            Sanitized string with only allowed characters
        """
        if not value:
            return ""

        # Convert to string
        str_value = str(value)
        
        # Replace backticks with single quotes for better readability
        str_value = str_value.replace("`", "'")

        # Allowed punctuation characters (matching FAM API safeString pattern exactly)
        # Note: colon (:) is explicitly NOT included
        allowed_punct = set("\\()_+@!#$%^&{}-=,.~'` ")

        # Keep only characters that match the safeString pattern
        sanitized = "".join(char for char in str_value if char in allowed_punct or char.isalnum() or ord(char) > 127)
        return sanitized

    @staticmethod
    def _truncate_string(value: Optional[str], max_length: int) -> str:
        """Sanitize and truncate string to maximum length.

        Args:
            value: String value to sanitize and truncate
            max_length: Maximum allowed length

        Returns:
            Sanitized and truncated string
        """
        if not value:
            return ""
        # First sanitize, then truncate
        sanitized = FAMToolPayload._sanitize_safe_string(value)
        return sanitized[:max_length]

    @staticmethod
    def _get_request_type(tool: Any) -> str:
        """Map ContextForge request_type to FAM MCPToolRequestType enum.

        Args:
            tool: ContextForge Tool ORM object

        Returns:
            MCPToolRequestType enum value (HTTP or SSE)
        """
        # ContextForge uses "SSE" or "HTTP" - map directly
        request_type = getattr(tool, "request_type", "SSE")
        if request_type and request_type.upper() in ["HTTP", "SSE"]:
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
        if hasattr(tool, "tags") and isinstance(tool.tags, list):
            tags = tool.tags[:50]  # Enforce maxItems: 50
        return tags

    @staticmethod
    def _build_schema(schema_dict: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Build MCPToolSchema from ContextForge schema.

        Ensures the schema matches FAM API MCPToolSchema structure:
        - type: string (required)
        - properties: map of property elements (optional)
        - required: array of required property names (optional)
        - description: string (optional)
        - format: string (optional)

        Filters out any attributes not in the MCPToolSchema specification.
        Handles anyOf schemas by extracting type from first option.

        Each property in 'properties' can be:
        - A primitive type (string, integer, number, boolean, array)
        - A nested object (MCPToolSchema with its own properties)

        Args:
            schema_dict: ContextForge schema dictionary

        Returns:
            MCPToolSchema compliant dictionary or None
        """
        if not schema_dict or not isinstance(schema_dict, dict):
            return None

        # Define allowed MCPToolSchema attributes per FAM API spec
        ALLOWED_SCHEMA_ATTRS = {"type", "properties", "required", "description", "format"}

        # Create a new schema with only allowed attributes
        schema = {}
        
        # Handle anyOf schemas first - extract type from first option
        # FAM API doesn't support anyOf, so we use the first type as the canonical type
        if "anyOf" in schema_dict and isinstance(schema_dict["anyOf"], list) and len(schema_dict["anyOf"]) > 0:
            first_option = schema_dict["anyOf"][0]
            if isinstance(first_option, dict):
                # Merge first option into schema_dict for processing
                for key in ALLOWED_SCHEMA_ATTRS:
                    if key in first_option:
                        schema_dict[key] = first_option[key]

        # Copy only allowed attributes from source schema
        for key in ALLOWED_SCHEMA_ATTRS:
            if key in schema_dict:
                # Sanitize and truncate description fields (max 300 chars per FAM API)
                if key == "description":
                    schema[key] = FAMToolPayload._truncate_string(schema_dict[key], 300)
                else:
                    schema[key] = schema_dict[key]

        # Ensure required 'type' field exists
        if "type" not in schema:
            schema["type"] = "object"

        # Ensure 'properties' field exists for object types
        if schema["type"] == "object" and "properties" not in schema:
            schema["properties"] = {}

        # Validate and normalize properties structure
        if "properties" in schema and isinstance(schema["properties"], dict):
            normalized_properties = {}
            for prop_name, prop_value in schema["properties"].items():
                if isinstance(prop_value, dict):
                    # Recursively normalize all property schemas (filters non-allowed attrs)
                    prop_value = FAMToolPayload._build_schema(prop_value) or prop_value

                    # Ensure each property has a 'type' field after normalization
                    if "type" not in prop_value:
                        prop_value["type"] = "string"  # Default to string

                    normalized_properties[prop_name] = prop_value
                else:
                    # If property value is not a dict, create a minimal schema
                    normalized_properties[prop_name] = {"type": "string"}

            schema["properties"] = normalized_properties

        # Recursively process items for array types
        if "items" in schema and isinstance(schema["items"], dict):
            schema["items"] = FAMToolPayload._build_schema(schema["items"]) or schema["items"]

        # Ensure 'required' is a list if present
        if "required" in schema and not isinstance(schema["required"], list):
            schema["required"] = []

        return schema

    @staticmethod
    def _build_annotations(tool: Any) -> Optional[Dict[str, Any]]:
        """Build MCPToolAnnotations from ContextForge tool.

        Args:
            tool: ContextForge Tool ORM object

        Returns:
            MCPToolAnnotations compliant dictionary or None
        """
        if not hasattr(tool, "annotations") or not tool.annotations:
            return None

        annotations = {}
        tool_annotations = tool.annotations

        # Map known annotation fields
        if "title" in tool_annotations:
            annotations["title"] = str(tool_annotations["title"])
        if "readOnlyHint" in tool_annotations:
            annotations["readOnlyHint"] = bool(tool_annotations["readOnlyHint"])
        if "destructiveHint" in tool_annotations:
            annotations["destructiveHint"] = bool(tool_annotations["destructiveHint"])
        if "idempotentHint" in tool_annotations:
            annotations["idempotentHint"] = bool(tool_annotations["idempotentHint"])
        if "openWorldHint" in tool_annotations:
            annotations["openWorldHint"] = bool(tool_annotations["openWorldHint"])

        return annotations if annotations else None

    @classmethod
    def build_create_payload(cls, tool: Any, server_id: str) -> Dict[str, Any]:
        """Build MCPToolCreate payload for POST request.

        Required fields: mcpServerId, name, inputSchema
        Optional fields: mcpToolId, description, requestType, outputSchema, annotations, tags, owner

        Includes all properties that FAM uses for change detection to ensure accurate sync.

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

        # Optional mcpToolId (critical for updates)
        if hasattr(tool, "id") and tool.id:
            payload["mcpToolId"] = cls._truncate_string(str(tool.id), 255)

        # Optional description (max 300 chars per FAM API validation)
        description = cls._truncate_string(tool.description or tool.original_description, 300)
        if description:
            payload["description"] = description

        # Optional requestType (always include for consistency)
        payload["requestType"] = cls._get_request_type(tool)

        # Optional outputSchema
        output_schema = cls._build_schema(tool.output_schema)
        if output_schema:
            payload["outputSchema"] = output_schema

        # Optional annotations
        annotations = cls._build_annotations(tool)
        if annotations:
            payload["annotations"] = annotations

        # Optional tags (always include even if empty for consistency)
        tags = cls._get_tags(tool)
        if tags:
            payload["tags"] = tags

        # Optional enabled flag (include for visibility control)
        if hasattr(tool, "enabled"):
            payload["enabled"] = bool(tool.enabled)

        # Optional custom_name for display purposes
        if hasattr(tool, "custom_name") and tool.custom_name:
            payload["customName"] = cls._truncate_string(tool.custom_name, 255)

        # Optional display_name
        if hasattr(tool, "display_name") and tool.display_name:
            payload["displayName"] = cls._truncate_string(tool.display_name, 255)

        # Optional title
        if hasattr(tool, "title") and tool.title:
            payload["title"] = cls._truncate_string(tool.title, 255)

        # Optional url
        if hasattr(tool, "url") and tool.url:
            payload["url"] = cls._truncate_string(tool.url, 767)

        # Optional headers
        if hasattr(tool, "headers") and tool.headers:
            payload["headers"] = tool.headers

        # Optional integration_type
        if hasattr(tool, "integration_type") and tool.integration_type:
            payload["integrationType"] = tool.integration_type

        # Optional visibility
        if hasattr(tool, "visibility") and tool.visibility:
            payload["visibility"] = tool.visibility

        # Optional team_id
        if hasattr(tool, "team_id") and tool.team_id:
            payload["teamId"] = tool.team_id

        # Optional owner_email
        if hasattr(tool, "owner_email") and tool.owner_email:
            payload["ownerEmail"] = tool.owner_email

        return payload

    @classmethod
    def build_update_payload(cls, tool: Any) -> Dict[str, Any]:
        """Build MCPToolUpdate payload for PUT request.

        mcpToolId is mandatory for bulk update operations.
        All other fields are optional in update schema.

        Includes all properties that FAM uses for change detection to ensure accurate sync.

        Args:
            tool: ContextForge Tool ORM object

        Returns:
            Dictionary matching MCPToolUpdate schema
        """
        payload: Dict[str, Any] = {}
        
        # Mandatory mcpToolId for bulk update
        if hasattr(tool, "id") and tool.id:
            payload["mcpToolId"] = cls._truncate_string(str(tool.id), 255)

        # Optional name
        name = cls._truncate_string(tool.original_name or tool.custom_name, 255)
        if name:
            payload["name"] = name

        # Optional description (max 300 chars per FAM API validation)
        description = cls._truncate_string(tool.description or tool.original_description, 300)
        if description:
            payload["description"] = description

        # Optional requestType (always include for consistency)
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

        # Optional tags (always include even if empty for consistency)
        tags = cls._get_tags(tool)
        if tags:
            payload["tags"] = tags

        # Optional enabled flag (include for visibility control)
        if hasattr(tool, "enabled"):
            payload["enabled"] = bool(tool.enabled)

        # Optional custom_name for display purposes
        if hasattr(tool, "custom_name") and tool.custom_name:
            payload["customName"] = cls._truncate_string(tool.custom_name, 255)

        # Optional display_name
        if hasattr(tool, "display_name") and tool.display_name:
            payload["displayName"] = cls._truncate_string(tool.display_name, 255)

        # Optional title
        if hasattr(tool, "title") and tool.title:
            payload["title"] = cls._truncate_string(tool.title, 255)

        # Optional url
        if hasattr(tool, "url") and tool.url:
            payload["url"] = cls._truncate_string(tool.url, 767)

        # Optional headers
        if hasattr(tool, "headers") and tool.headers:
            payload["headers"] = tool.headers

        # Optional integration_type
        if hasattr(tool, "integration_type") and tool.integration_type:
            payload["integrationType"] = tool.integration_type

        # Optional visibility
        if hasattr(tool, "visibility") and tool.visibility:
            payload["visibility"] = tool.visibility

        # Optional team_id
        if hasattr(tool, "team_id") and tool.team_id:
            payload["teamId"] = tool.team_id

        # Optional owner_email
        if hasattr(tool, "owner_email") and tool.owner_email:
            payload["ownerEmail"] = tool.owner_email

        return payload
