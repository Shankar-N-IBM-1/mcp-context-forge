"""Send Heartbeat Activity.

Sends runtime heartbeat to FAM periodically.
"""

# Local
from ..fam import FAMAssetCatalogClient
from ..models import ActivityContext
from ..utils import RetryConfig, SyncError, with_retry
from .base import AbstractScheduledActivity


class SendHeartbeatActivity(AbstractScheduledActivity):
    """Activity for sending runtime heartbeat to FAM.

    Attributes:
        context: Shared activity context
        fam_client: FAM API client
        heartbeat_interval: Interval in seconds
    """

    def __init__(self, context: ActivityContext, fam_client: FAMAssetCatalogClient, heartbeat_interval: int = 60):
        """Initialize send heartbeat activity.

        Args:
            context: Shared activity context
            fam_client: FAM API client
            heartbeat_interval: Heartbeat interval in seconds
        """
        super().__init__(context)
        self._fam_client = fam_client
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
        print(f"\n{'='*70}")
        print(f"[ACTIVITY] Send Heartbeat - Starting")
        print(f"{'='*70}")
        
        try:
            # Send heartbeat with retry logic
            print(f"[ACTIVITY] Sending heartbeat to FAM...")
            await with_retry(self._send_heartbeat, retry_config=RetryConfig(max_attempts=2, initial_delay=0.5), operation_name="Send Heartbeat")

            # Track success
            self._consecutive_failures = 0
            self._total_heartbeats_sent += 1

            print(f"[ACTIVITY] ✓ Heartbeat sent successfully")
            print(f"[ACTIVITY]   Total heartbeats sent: {self._total_heartbeats_sent}")
            self.logger.debug(f"Heartbeat sent successfully (total: {self._total_heartbeats_sent})")
            print(f"[ACTIVITY] Send Heartbeat - Complete")
            print(f"{'='*70}\n")

        except Exception as e:
            self._consecutive_failures += 1
            print(f"[ACTIVITY] ✗ Heartbeat failed (consecutive failures: {self._consecutive_failures})")
            error_msg = f"Failed to send heartbeat (consecutive failures: {self._consecutive_failures}): {e}"
            self.logger.error(error_msg, exc_info=True)
            print(f"{'='*70}\n")
            raise SyncError(error_msg, e)

    async def _send_heartbeat(self) -> None:
        """Send heartbeat to FAM.

        Raises:
            Exception: If heartbeat fails
        """
        print(f"[ACTION] Calling FAM API: POST /api/engine/v2/runtimes/heartbeat")
        print(f"[ACTION]   Runtime ID: {self.context.runtime_id}")
        
        success = await self._fam_client.send_heartbeat(self.context.runtime_id)
        
        if success:
            print(f"[ACTION] ✓ FAM API call successful")
        else:
            print(f"[ACTION] ✗ FAM API call failed")
            raise Exception("Heartbeat failed")

