"""Check Runtime Health Activity.

Periodically checks ContextForge runtime health and resource usage.
Follows webMethods Agent SDK HealthCheckActivity pattern.

Copyright 2025
SPDX-License-Identifier: Apache-2.0
"""

# Standard
from datetime import datetime, timezone
import logging
from typing import Any, Dict

# Third-Party
import psutil

# First-Party
from mcpgateway.db import Server, SessionLocal, Tool

# Local
from ..models import ActivityContext
from .base import AbstractScheduledActivity

logger = logging.getLogger(__name__)


class CheckRuntimeHealthActivity(AbstractScheduledActivity):
    """Activity for checking ContextForge runtime health.

    Following webMethods SDK pattern, this activity:
    1. Checks database connectivity
    2. Monitors resource usage (CPU, memory)
    3. Counts active servers and tools
    4. Tracks health metrics
    5. Logs health status

    Attributes:
        context: Shared activity context
        check_interval: Interval in seconds
    """

    def __init__(self, context: ActivityContext, check_interval: int = 60):
        """Initialize runtime health check activity.

        Args:
            context: Shared activity context
            check_interval: Health check interval in seconds (default: 60)
        """
        super().__init__(context)
        self._check_interval = check_interval
        self._total_checks = 0
        self._successful_checks = 0
        self._last_check_time: datetime | None = None
        self._last_server_count = 0
        self._last_tool_count = 0
        self._last_cpu_percent = 0.0
        self._last_memory_percent = 0.0

    def get_interval_seconds(self) -> int:
        """Get the health check interval.

        Returns:
            Interval in seconds
        """
        return self._check_interval

    async def perform(self) -> None:
        """Check runtime health.

        Raises:
            Exception: If health check fails critically
        """
        try:
            # Check database connectivity and count resources
            server_count, tool_count = await self._check_database_health()

            # Check system resources
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory_percent = psutil.virtual_memory().percent

            # Update statistics
            self._total_checks += 1
            self._successful_checks += 1
            self._last_check_time = datetime.now(timezone.utc)
            self._last_server_count = server_count
            self._last_tool_count = tool_count
            self._last_cpu_percent = cpu_percent
            self._last_memory_percent = memory_percent

            logger.info(f"Runtime health check passed - " f"servers: {server_count}, tools: {tool_count}, " f"CPU: {cpu_percent:.1f}%, Memory: {memory_percent:.1f}%")

            # Alert on high resource usage
            if cpu_percent > 80:
                logger.warning(f"High CPU usage detected: {cpu_percent:.1f}%")
            if memory_percent > 80:
                logger.warning(f"High memory usage detected: {memory_percent:.1f}%")

        except Exception as e:
            self._total_checks += 1
            logger.error(f"Runtime health check failed: {e}", exc_info=True)

    async def _check_database_health(self) -> tuple[int, int]:
        """Check database connectivity and count resources.

        Returns:
            Tuple of (server_count, tool_count)

        Raises:
            Exception: If database check fails
        """
        try:
            with SessionLocal() as db:
                server_count = db.query(Server).count()
                tool_count = db.query(Tool).count()
                return server_count, tool_count
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            raise

    def get_health_stats(self) -> Dict[str, Any]:
        """Get health check statistics.

        Returns:
            Dictionary with health stats
        """
        success_rate = (self._successful_checks / self._total_checks * 100) if self._total_checks > 0 else 0.0

        return {
            "total_checks": self._total_checks,
            "successful_checks": self._successful_checks,
            "success_rate": success_rate,
            "last_check_time": (self._last_check_time.isoformat() if self._last_check_time else None),
            "server_count": self._last_server_count,
            "tool_count": self._last_tool_count,
            "cpu_percent": self._last_cpu_percent,
            "memory_percent": self._last_memory_percent,
            "is_healthy": (self._last_cpu_percent < 90 and self._last_memory_percent < 90),
            "interval_seconds": self._check_interval,
        }


# Made with Bob
