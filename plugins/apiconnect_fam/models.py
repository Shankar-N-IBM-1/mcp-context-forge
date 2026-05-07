"""Data Models for Server Monitor Plugin.

Defines core data models used throughout the plugin, following patterns
from webMethods Agent SDK.

Copyright 2025
SPDX-License-Identifier: Apache-2.0
"""

from datetime import datetime, timezone
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


class ActivityStatistics(BaseModel):
    """Statistics for an activity execution.
    
    Tracks execution metrics for monitoring and debugging.
    
    Attributes:
        activity_name: Name of the activity
        status: Current status
        total_executions: Total number of executions
        successful_executions: Number of successful executions
        failed_executions: Number of failed executions
        last_execution_time: Timestamp of last execution
        last_success_time: Timestamp of last successful execution
        last_failure_time: Timestamp of last failed execution
        last_error: Last error message (if any)
        average_duration_ms: Average execution duration in milliseconds
    """
    
    activity_name: str
    status: ActivityStatus = ActivityStatus.PENDING
    total_executions: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    last_execution_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    last_failure_time: Optional[datetime] = None
    last_error: Optional[str] = None
    average_duration_ms: float = 0.0
    
    def record_execution(
        self,
        success: bool,
        duration_ms: float,
        error: Optional[str] = None
    ) -> None:
        """Record an activity execution.
        
        Args:
            success: Whether the execution was successful
            duration_ms: Execution duration in milliseconds
            error: Error message if execution failed
        """
        now = datetime.now(timezone.utc)
        self.total_executions += 1
        self.last_execution_time = now
        
        if success:
            self.successful_executions += 1
            self.last_success_time = now
            self.status = ActivityStatus.SUCCESS
        else:
            self.failed_executions += 1
            self.last_failure_time = now
            self.last_error = error
            self.status = ActivityStatus.FAILED
        
        # Update average duration (running average)
        if self.total_executions == 1:
            self.average_duration_ms = duration_ms
        else:
            self.average_duration_ms = (
                (self.average_duration_ms * (self.total_executions - 1) + duration_ms)
                / self.total_executions
            )
    
    def get_success_rate(self) -> float:
        """Calculate success rate as percentage.
        
        Returns:
            Success rate (0.0 to 100.0)
        """
        if self.total_executions == 0:
            return 0.0
        return (self.successful_executions / self.total_executions) * 100.0


class SyncStatistics(BaseModel):
    """Overall synchronization statistics.
    
    Aggregates statistics across all activities.
    
    Attributes:
        runtime_id: Runtime ID
        uptime_seconds: Agent uptime in seconds
        activities: Statistics for each activity
        total_servers_synced: Total servers synced
        total_tools_synced: Total tools synced
        total_metrics_sent: Total metrics sent
        total_heartbeats_sent: Total heartbeats sent
    """
    
    runtime_id: str
    uptime_seconds: int = 0
    activities: Dict[str, ActivityStatistics] = Field(default_factory=dict)
    total_servers_synced: int = 0
    total_tools_synced: int = 0
    total_metrics_sent: int = 0
    total_heartbeats_sent: int = 0
    
    def get_activity_stats(self, activity_name: str) -> ActivityStatistics:
        """Get or create statistics for an activity.
        
        Args:
            activity_name: Name of the activity
            
        Returns:
            Activity statistics
        """
        if activity_name not in self.activities:
            self.activities[activity_name] = ActivityStatistics(
                activity_name=activity_name
            )
        return self.activities[activity_name]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization.
        
        Returns:
            Dictionary representation
        """
        return {
            "runtime_id": self.runtime_id,
            "uptime_seconds": self.uptime_seconds,
            "activities": {
                name: {
                    "status": stats.status.value,
                    "total_executions": stats.total_executions,
                    "successful_executions": stats.successful_executions,
                    "failed_executions": stats.failed_executions,
                    "success_rate": stats.get_success_rate(),
                    "average_duration_ms": stats.average_duration_ms,
                    "last_execution_time": (
                        stats.last_execution_time.isoformat()
                        if stats.last_execution_time else None
                    ),
                    "last_error": stats.last_error
                }
                for name, stats in self.activities.items()
            },
            "totals": {
                "servers_synced": self.total_servers_synced,
                "tools_synced": self.total_tools_synced,
                "metrics_sent": self.total_metrics_sent,
                "heartbeats_sent": self.total_heartbeats_sent
            }
        }


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


# Made with Bob