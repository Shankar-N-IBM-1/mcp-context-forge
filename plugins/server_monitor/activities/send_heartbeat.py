"""Send Heartbeat Activity.

Sends runtime heartbeat to FAM periodically.
Follows webMethods Agent SDK SendHeartbeatActivity pattern.

Copyright 2025
SPDX-License-Identifier: Apache-2.0
"""

from datetime import datetime, timezone

from ..fam_client import FAMAssetCatalogClient
from ..handlers import TimestampStorageHandler
from ..models import ActivityContext
from ..utils import SyncError, with_retry, RetryConfig
from .base import AbstractScheduledActivity


class SendHeartbeatActivity(AbstractScheduledActivity):
    """Activity for sending runtime heartbeat to FAM.
    
    Following webMethods SDK pattern, this activity:
    1. Sends heartbeat at configured interval
    2. Updates timestamp storage
    3. Tracks success/failure statistics
    4. Uses retry logic for transient failures
    
    Attributes:
        context: Shared activity context
        fam_client: FAM API client
        timestamp_handler: Timestamp storage handler
        heartbeat_interval: Interval in seconds
    """
    
    def __init__(
        self,
        context: ActivityContext,
        fam_client: FAMAssetCatalogClient,
        timestamp_handler: TimestampStorageHandler,
        heartbeat_interval: int = 60
    ):
        """Initialize send heartbeat activity.
        
        Args:
            context: Shared activity context
            fam_client: FAM API client
            timestamp_handler: Timestamp storage handler
            heartbeat_interval: Heartbeat interval in seconds
        """
        super().__init__(context)
        self._fam_client = fam_client
        self._timestamp_handler = timestamp_handler
        self._heartbeat_interval = heartbeat_interval
        self._consecutive_failures = 0
        self._total_heartbeats_sent = 0
    
    def get_interval_seconds(self) -> int:
        """Get the heartbeat interval.
        
        Returns:
            Interval in seconds
        """
        return self._heartbeat_interval
    
    async def perform(self) -> None:
        """Send heartbeat to FAM.
        
        Raises:
            SyncError: If heartbeat fails after retries
        """
        try:
            # Send heartbeat with retry logic
            await with_retry(
                self._send_heartbeat,
                retry_config=RetryConfig(max_attempts=2, initial_delay=0.5),
                operation_name="Send Heartbeat"
            )
            
            # Update timestamp storage
            current_time_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
            self._timestamp_handler.save_timestamp(
                self._timestamp_handler.KEY_HEARTBEAT,
                current_time_ms
            )
            
            # Track success
            self._consecutive_failures = 0
            self._total_heartbeats_sent += 1
            
            self.logger.debug(
                f"Heartbeat sent successfully (total: {self._total_heartbeats_sent})"
            )
            
        except Exception as e:
            self._consecutive_failures += 1
            error_msg = f"Failed to send heartbeat (consecutive failures: {self._consecutive_failures}): {e}"
            self.logger.error(error_msg, exc_info=True)
            raise SyncError(error_msg, e)
    
    async def _send_heartbeat(self) -> None:
        """Send heartbeat to FAM.
        
        Raises:
            Exception: If heartbeat fails
        """
        await self._fam_client.send_heartbeat(self.context.runtime_id)
    
    def get_heartbeat_stats(self) -> dict:
        """Get heartbeat statistics.
        
        Returns:
            Dictionary with heartbeat stats
        """
        return {
            "total_sent": self._total_heartbeats_sent,
            "consecutive_failures": self._consecutive_failures,
            "interval_seconds": self._heartbeat_interval,
            "last_execution": (
                self.last_execution_time
                if self.last_execution_time
                else None
            )
        }


# Made with Bob