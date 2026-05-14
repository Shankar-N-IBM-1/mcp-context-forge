"""Register Runtime Activity.

Handles runtime registration with FAM.

"""

# Standard
from typing import Optional

# Local
from ..fam import FAMAssetCatalogClient
from ..models import ActivityContext, ReregistrationReport
from ..utils import RegistrationError, RetryConfig, with_retry
from .base import AbstractActivity


class RegisterRuntimeActivity(AbstractActivity):
    """Activity for registering runtime with FAM.

    Attributes:
        context: Shared activity context
        fam_client: FAM API client
        runtime_config: Runtime configuration
    """

    def __init__(self, context: ActivityContext, fam_client: FAMAssetCatalogClient, runtime_config: dict):
        """Initialize register runtime activity.

        Args:
            context: Shared activity context
            fam_client: FAM API client
            runtime_config: Runtime configuration dictionary
        """
        super().__init__(context)
        self._fam_client = fam_client
        self._runtime_config = runtime_config
        self._runtime_id: Optional[str] = None

    async def perform(self) -> None:
        """Execute runtime registration.

        Raises:
            RegistrationError: If registration fails
        """
        print(f"\n{'='*70}")
        print(f"[ACTIVITY] Runtime Registration - Starting")
        print(f"{'='*70}")
        
        self.logger.info("Registering runtime with FAM")

        try:
            # Register runtime with retry logic
            print(f"[ACTIVITY] Attempting runtime registration with FAM...")
            report = await with_retry(self._register_runtime, retry_config=RetryConfig(max_attempts=3, initial_delay=2.0), operation_name="Runtime Registration")

            if not report or not report.runtime_id:
                print(f"[ACTIVITY] ✗ Runtime registration failed - no runtime ID returned")
                raise RegistrationError("Runtime registration returned no runtime ID")

            self._runtime_id = report.runtime_id
            print(f"[ACTIVITY] ✓ Runtime registered successfully")
            print(f"[ACTIVITY]   Runtime ID: {report.runtime_id}")
            print(f"[ACTIVITY]   Status Code: {report.status_code}")
            
            # Check if this is a re-registration (200/409) or first registration (201)
            if report.status_code in (200, 409):
                print(f"[ACTIVITY]   Re-registration detected (status {report.status_code})")
                if any([report.last_heartbeat_time, report.last_metrics_time, report.last_asset_sync_time]):
                    print(f"[ACTIVITY]   Last heartbeat: {report.last_heartbeat_time}")
                    print(f"[ACTIVITY]   Last metrics: {report.last_metrics_time}")
                    print(f"[ACTIVITY]   Last asset sync: {report.last_asset_sync_time}")
            else:
                print(f"[ACTIVITY]   First-time registration (status {report.status_code})")
            
            self.logger.info(f"Runtime registered successfully with ID: {report.runtime_id}, status: {report.status_code}")

            # Update context with runtime ID
            self.context.runtime_id = report.runtime_id
            
            # TODO: Implement recovery handler for re-registration
            # When re-registration is detected (status 200/409), should trigger recovery for:
            # - Missed heartbeats (send INACTIVE heartbeats for missed intervals)
            # - Missed metrics (send historical metrics data)
            # - Missed asset syncs (perform full server/tool sync)
            # See: handlers/recovery_handler.py for implementation reference
            
            print(f"[ACTIVITY] Runtime Registration - Complete")
            print(f"{'='*70}\n")

        except Exception as e:
            error_msg = f"Runtime registration failed: {e}"
            self.logger.error(error_msg, exc_info=True)
            raise RegistrationError(error_msg, e)

    async def _register_runtime(self) -> Optional[ReregistrationReport]:
        """Register runtime with FAM.

        Returns:
            ReregistrationReport with runtime ID and sync timestamps, or None if failed

        Raises:
            Exception: If registration fails
        """
        print(f"[ACTION] Calling FAM API: POST /api/assetcatalog/v2/runtimes")
        print(f"[ACTION]   Runtime Name: {self._runtime_config.get('name', 'ContextForge Gateway')}")
        print(f"[ACTION]   Runtime Type: {self._runtime_config.get('type', 'WEBMETHODS_GATEWAY')}")
        
        report = await self._fam_client.register_runtime(
            name=self._runtime_config.get("name", "ContextForge Gateway"),
            description=self._runtime_config.get("description", "ContextForge MCP Gateway Runtime"),
            runtime_type=self._runtime_config.get("type", "WEBMETHODS_GATEWAY"),
            deployment_type=self._runtime_config.get("deployment_type", "ON_PREMISE"),
            region=self._runtime_config.get("region"),
            location=self._runtime_config.get("location"),
            host=self._runtime_config.get("host"),
            tags=self._runtime_config.get("tags", []),
            capacity_value=self._runtime_config.get("capacity_value", "100"),
            capacity_unit=self._runtime_config.get("capacity_unit", "per minute"),
            heartbeat_interval=self._runtime_config.get("heartbeat_interval", 6000),
        )

        if report and report.runtime_id:
            print(f"[ACTION] ✓ FAM API call successful")
        else:
            print(f"[ACTION] ✗ FAM API call failed")
            raise RegistrationError("FAM API returned no report or runtime ID")

        return report

    def get_runtime_id(self) -> Optional[str]:
        """Get the registered runtime ID.

        Returns:
            Runtime ID if registration succeeded, None otherwise
        """
        return self._runtime_id
