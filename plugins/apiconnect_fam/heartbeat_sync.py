"""Heartbeat Synchronization Module.

Handles sending periodic heartbeats to FAM for the registered runtime.

Copyright 2025
SPDX-License-Identifier: Apache-2.0
"""

from datetime import datetime, timezone
import logging
from typing import Optional

from .fam import FAMAssetCatalogClient

logger = logging.getLogger(__name__)


class HeartbeatSyncTask:
    """Task for sending heartbeats to FAM.
    
    Handles:
    - Sending periodic heartbeat signals to FAM
    - Tracking last heartbeat time
    - Logging heartbeat status
    """
    
    def __init__(
        self,
        fam_client: FAMAssetCatalogClient,
        runtime_id: str,
        heartbeat_interval: int = 60
    ):
        """Initialize heartbeat sync task.
        
        Args:
            fam_client: FAM API client for heartbeat operations
            runtime_id: Runtime ID to send heartbeats for
            heartbeat_interval: How often to send heartbeats (in seconds)
        """
        self._fam_client = fam_client
        self._runtime_id = runtime_id
        self._heartbeat_interval = heartbeat_interval
        self._last_heartbeat: Optional[datetime] = None
        self._heartbeat_counter = 0
        self._failed_heartbeats = 0
    
    async def execute(self) -> None:
        """Execute heartbeat synchronization task.
        
        Sends heartbeat to FAM and tracks success/failure.
        """
        try:
            # Check if it's time to send heartbeat
            if not self._should_send():
                return
            
            # Send heartbeat
            await self._send_heartbeat()
            
        except Exception as e:
            logger.error(f"Error in heartbeat sync task: {e}", exc_info=True)
    
    def _should_send(self) -> bool:
        """Check if it's time to send a heartbeat.
        
        Returns:
            True if heartbeat should be sent, False otherwise
        """
        if self._last_heartbeat is None:
            return True
        
        elapsed = (datetime.now(timezone.utc) - self._last_heartbeat).total_seconds()
        return elapsed >= self._heartbeat_interval
    
    async def _send_heartbeat(self) -> None:
        """Send heartbeat to FAM.
        
        Updates heartbeat tracking on success/failure.
        """
        success = await self._fam_client.send_heartbeat(self._runtime_id)
        
        if success:
            self._last_heartbeat = datetime.now(timezone.utc)
            self._heartbeat_counter += 1
            self._failed_heartbeats = 0  # Reset failure counter on success
            logger.info(
                f"Heartbeat #{self._heartbeat_counter} sent successfully "
                f"for runtime {self._runtime_id}"
            )
        else:
            self._failed_heartbeats += 1
            logger.warning(
                f"Failed to send heartbeat for runtime {self._runtime_id} "
                f"(consecutive failures: {self._failed_heartbeats})"
            )
    
    def get_stats(self) -> dict:
        """Get heartbeat statistics.
        
        Returns:
            Dictionary with heartbeat stats
        """
        return {
            "total_heartbeats": self._heartbeat_counter,
            "failed_heartbeats": self._failed_heartbeats,
            "last_heartbeat": self._last_heartbeat.isoformat() if self._last_heartbeat else None,
            "runtime_id": self._runtime_id
        }

# Made with Bob
