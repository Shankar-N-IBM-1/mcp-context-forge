"""Data Models for Server Monitor Plugin.

Defines core data models used throughout the plugin, following patterns
from webMethods Agent SDK.

Copyright 2025
SPDX-License-Identifier: Apache-2.0
"""

from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


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
    """Report received from FAM on runtime registration.
    
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
    status_code: int = Field(
        description="HTTP status code (201=created, 200/409=re-registered)"
    )
    last_registration_time: Optional[int] = Field(
        default=None,
        description="Last registration timestamp in milliseconds"
    )
    last_heartbeat_time: Optional[int] = Field(
        default=None,
        description="Last heartbeat timestamp in milliseconds"
    )
    last_metrics_time: Optional[int] = Field(
        default=None,
        description="Last metrics sync timestamp in milliseconds"
    )
    last_asset_sync_time: Optional[int] = Field(
        default=None,
        description="Last asset sync timestamp in milliseconds"
    )
    
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
        fam_base_url: Base URL for FAM API
        config: Plugin configuration dictionary
    """
    
    runtime_id: str
    fam_base_url: str
    config: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        arbitrary_types_allowed = True


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
        """Convert to FAM API payload format.
        
        Returns:
            Dictionary for FAM heartbeat API
        """
        return {
            "runtimeId": self.runtime_id,
            "created": self.created,
            "active": 0  # 0 = inactive, 1 = active
        }


