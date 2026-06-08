"""Location: ./plugins/apiconnect_fam/models.py
Copyright 2025
SPDX-License-Identifier: Apache-2.0
Authors: Shankar N

Data Models for Server Monitor Plugin.
Defines core data models used throughout the plugin.
"""

# Standard
from enum import Enum
from typing import Any, Dict, Optional

# Third-Party
from pydantic import BaseModel, ConfigDict, Field, field_validator

# Constants
RUNTIME_TYPE = "MCP_CONTEXT_FORGE"  # Fixed runtime type for ContextForge


class TLSConfig(BaseModel):
    """TLS/SSL configuration for secure HTTPS connections.
    
    Supports both one-way SSL (server authentication only) and mutual TLS
    (two-way SSL with client certificate authentication).
    
    Attributes:
        truststore_path: Path to truststore file (JKS, PKCS12, or PEM)
        truststore_password: Password for truststore (optional for PEM)
        truststore_type: Truststore type (JKS, PKCS12, PEM) - default: JKS
        keystore_path: Path to keystore file for mutual TLS (optional)
        keystore_password: Password for keystore (required if keystore_path provided)
        keystore_type: Keystore type (JKS, PKCS12, PEM) - default: JKS
        key_alias: Certificate alias in keystore (optional, for mutual TLS)
        key_password: Private key password (optional, defaults to keystore_password)
    """
    
    truststore_path: str = Field(description="Path to truststore file")
    truststore_password: Optional[str] = Field(default=None, description="Truststore password")
    truststore_type: str = Field(default="JKS", description="Truststore type (JKS, PKCS12, PEM)")
    
    keystore_path: Optional[str] = Field(default=None, description="Path to keystore file for mutual TLS")
    keystore_password: Optional[str] = Field(default=None, description="Keystore password")
    keystore_type: str = Field(default="JKS", description="Keystore type (JKS, PKCS12, PEM)")
    
    key_alias: Optional[str] = Field(default=None, description="Certificate alias in keystore")
    key_password: Optional[str] = Field(default=None, description="Private key password")
    
    @field_validator("truststore_type", "keystore_type")
    @classmethod
    def validate_store_type(cls, v: str) -> str:
        """Validate store type is one of the supported formats."""
        allowed = {"JKS", "PKCS12", "PEM"}
        v_upper = v.upper()
        if v_upper not in allowed:
            raise ValueError(f"Store type must be one of {allowed}, got: {v}")
        return v_upper
    
    @field_validator("keystore_password", mode="after")
    @classmethod
    def validate_keystore_password(cls, v: Optional[str]) -> Optional[str]:
        """Validate keystore_password is provided if keystore_path is set.
        
        Note: This validator runs after model initialization, so we can't access
        other fields here. The validation is done in the model_validator instead.
        """
        return v
    
    @field_validator("keystore_path", mode="after")
    @classmethod
    def validate_keystore_config(cls, v: Optional[str]) -> Optional[str]:
        """Validate keystore configuration consistency."""
        # Validation will be done in model_validator to access all fields
        return v
    
    def is_mutual_tls(self) -> bool:
        """Check if this configuration enables mutual TLS (two-way SSL).
        
        Returns:
            True if keystore is configured for client certificate authentication
        """
        return bool(self.keystore_path and self.keystore_password)


class ActivityStatus(str, Enum):
    """Status of an activity execution."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class HeartbeatStatus(str, Enum):
    """Status of runtime heartbeat."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    UNKNOWN = "unknown"


class ReregistrationReport(BaseModel):
    """Report received from IBM API Connect Federated API Management on runtime registration.

    Contains timestamps of last successful sync operations,
    used to trigger recovery of missed data.

    Attributes:
        runtime_id: The registered runtime ID
        status_code: HTTP status code from registration (201=created, 200/409=re-registered)
        last_registration_time: Timestamp of last registration (milliseconds)
        last_heartbeat_time: Timestamp of last heartbeat (milliseconds)
        last_metrics_time: Timestamp of last metrics sync (milliseconds)
        last_asset_sync_time: Timestamp of last asset sync (milliseconds)
    """

    runtime_id: str
    status_code: int = Field(description="HTTP status code (201=created, 200/409=re-registered)")
    last_registration_time: Optional[int] = Field(default=None, description="Last registration timestamp in milliseconds")
    last_heartbeat_time: Optional[int] = Field(default=None, description="Last heartbeat timestamp in milliseconds")
    last_metrics_time: Optional[int] = Field(default=None, description="Last metrics sync timestamp in milliseconds")
    last_asset_sync_time: Optional[int] = Field(default=None, description="Last asset sync timestamp in milliseconds")

    def is_reregistration(self) -> bool:
        """Check if this is a re-registration (status 200 or 409).

        Returns:
            True if status code is 200 or 409 (re-registration), False otherwise (201=first-time)
        """
        return self.status_code in (200, 409)


class ActivityContext(BaseModel):
    """Context shared across all activities.

    Provides access to shared resources and configuration
    needed by activities.

    Attributes:
        runtime_id: Runtime ID for this agent
        fam_base_url: Base URL for IBM API Connect Federated API Management API
        config: Plugin configuration dictionary
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    runtime_id: str
    fam_base_url: str
    config: Dict[str, Any] = Field(default_factory=dict)


class InactiveHeartbeat(BaseModel):
    """Represents an inactive heartbeat for recovery.

    Used when sending missed heartbeats during recovery.

    Attributes:
        runtime_id: Runtime ID
        created: Timestamp in milliseconds
        status: Heartbeat status (INACTIVE)
    """

    runtime_id: str
    created: int
    status: HeartbeatStatus = HeartbeatStatus.INACTIVE

    def to_payload(self) -> Dict[str, Any]:
        """Convert to IBM API Connect Federated API Management API payload format.

        Returns:
            Dictionary for IBM API Connect Federated API Management heartbeat API
        """
        return {"runtimeId": self.runtime_id, "created": self.created, "active": 0}  # 0 = inactive, 1 = active
