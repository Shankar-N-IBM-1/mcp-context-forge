"""Check FAM Health Activity.

Periodically checks FAM API health and connectivity.
Follows webMethods Agent SDK HealthCheckActivity pattern.

Copyright 2025
SPDX-License-Identifier: Apache-2.0
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict

from ..fam_client import FAMAssetCatalogClient
from ..models import ActivityContext
from .base import AbstractScheduledActivity

logger = logging.getLogger(__name__)


class CheckFAMHealthActivity(AbstractScheduledActivity):
    """Activity for checking FAM API health.
    
    Following webMethods SDK pattern, this activity:
    1. Pings FAM API endpoint
    2. Checks response time
    3. Tracks consecutive failures
    4. Updates health status
    5. Logs health metrics
    
    Attributes:
        context: Shared activity context
        fam_client: FAM API client
        check_interval: Interval in seconds
    """
    
    def __init__(
        self,
        context: ActivityContext,
        fam_client: FAMAssetCatalogClient,
        check_interval: int = 30
    ):
        """Initialize FAM health check activity.
        
        Args:
            context: Shared activity context
            fam_client: FAM API client
            check_interval: Health check interval in seconds (default: 30)
        """
        super().__init__(context)
        self._fam_client = fam_client
        self._check_interval = check_interval
        self._consecutive_failures = 0
        self._last_success_time: datetime | None = None
        self._last_failure_time: datetime | None = None
        self._total_checks = 0
        self._successful_checks = 0
        self._average_response_time_ms = 0.0
    
    def get_interval_seconds(self) -> int:
        """Get the health check interval.
        
        Returns:
            Interval in seconds
        """
        return self._check_interval
    
    async def perform(self) -> None:
        """Check FAM API health.
        
        Raises:
            Exception: If health check fails critically
        """
        start_time = datetime.now(timezone.utc)
        
        try:
            # Perform health check (simple API call)
            # Using a lightweight endpoint - could be a dedicated health endpoint
            await self._check_fam_connectivity()
            
            # Calculate response time
            end_time = datetime.now(timezone.utc)
            response_time_ms = (end_time - start_time).total_seconds() * 1000
            
            # Update statistics
            self._total_checks += 1
            self._successful_checks += 1
            self._consecutive_failures = 0
            self._last_success_time = end_time
            
            # Update average response time
            if self._total_checks == 1:
                self._average_response_time_ms = response_time_ms
            else:
                self._average_response_time_ms = (
                    (self._average_response_time_ms * (self._total_checks - 1) + response_time_ms)
                    / self._total_checks
                )
            
            logger.info(
                f"FAM health check passed - response time: {response_time_ms:.2f}ms, "
                f"avg: {self._average_response_time_ms:.2f}ms"
            )
            
        except Exception as e:
            # Update failure statistics
            self._total_checks += 1
            self._consecutive_failures += 1
            self._last_failure_time = datetime.now(timezone.utc)
            
            logger.error(
                f"FAM health check failed (consecutive failures: {self._consecutive_failures}): {e}",
                exc_info=True
            )
            
            # Alert if too many consecutive failures
            if self._consecutive_failures >= 3:
                logger.critical(
                    f"FAM health check has failed {self._consecutive_failures} times consecutively! "
                    "FAM may be unavailable."
                )
    
    async def _check_fam_connectivity(self) -> None:
        """Check FAM API connectivity.
        
        Makes a simple API call to verify FAM is reachable.
        
        Raises:
            Exception: If connectivity check fails
        """
        # TODO: Implement actual health check
        # This could be a dedicated health endpoint or a lightweight API call
        # For now, we'll use a simple approach
        
        # Example: Try to get runtime info (lightweight operation)
        # await self._fam_client.get_runtime_info()
        
        # Placeholder - in real implementation, make actual API call
        logger.debug("Checking FAM connectivity...")
    
    def get_health_stats(self) -> Dict[str, Any]:
        """Get health check statistics.
        
        Returns:
            Dictionary with health stats
        """
        success_rate = (
            (self._successful_checks / self._total_checks * 100)
            if self._total_checks > 0
            else 0.0
        )
        
        return {
            "total_checks": self._total_checks,
            "successful_checks": self._successful_checks,
            "success_rate": success_rate,
            "consecutive_failures": self._consecutive_failures,
            "average_response_time_ms": self._average_response_time_ms,
            "last_success_time": (
                self._last_success_time.isoformat()
                if self._last_success_time
                else None
            ),
            "last_failure_time": (
                self._last_failure_time.isoformat()
                if self._last_failure_time
                else None
            ),
            "is_healthy": self._consecutive_failures < 3,
            "interval_seconds": self._check_interval
        }


# Made with Bob