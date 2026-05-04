"""Register Runtime Activity.

Handles runtime registration with FAM and triggers recovery if needed.
Follows webMethods Agent SDK RegisterRuntimeActivity pattern.

Copyright 2025
SPDX-License-Identifier: Apache-2.0
"""

from typing import Optional

from ..fam_client import FAMAssetCatalogClient
from ..handlers import RecoveryHandler, TimestampStorageHandler
from ..models import ActivityContext, ReregistrationReport
from ..utils import RegistrationError, with_retry, RetryConfig
from .base import AbstractActivity


class RegisterRuntimeActivity(AbstractActivity):
    """Activity for registering runtime with FAM.
    
    Following webMethods SDK pattern, this activity:
    1. Registers runtime with FAM
    2. Receives re-registration report with last sync times
    3. Updates timestamp storage
    4. Triggers recovery tasks if needed
    
    Attributes:
        context: Shared activity context
        fam_client: FAM API client
        timestamp_handler: Timestamp storage handler
        recovery_handler: Recovery handler
        runtime_config: Runtime configuration
    """
    
    def __init__(
        self,
        context: ActivityContext,
        fam_client: FAMAssetCatalogClient,
        timestamp_handler: TimestampStorageHandler,
        recovery_handler: RecoveryHandler,
        runtime_config: dict
    ):
        """Initialize register runtime activity.
        
        Args:
            context: Shared activity context
            fam_client: FAM API client
            timestamp_handler: Timestamp storage handler
            recovery_handler: Recovery handler
            runtime_config: Runtime configuration dictionary
        """
        super().__init__(context)
        self._fam_client = fam_client
        self._timestamp_handler = timestamp_handler
        self._recovery_handler = recovery_handler
        self._runtime_config = runtime_config
        self._runtime_id: Optional[str] = None
    
    async def perform(self) -> None:
        """Execute runtime registration.
        
        Raises:
            RegistrationError: If registration fails
        """
        self.logger.info("Registering runtime with FAM")
        
        try:
            # Register runtime with retry logic
            runtime_id = await with_retry(
                self._register_runtime,
                retry_config=RetryConfig(max_attempts=3, initial_delay=2.0),
                operation_name="Runtime Registration"
            )
            
            if not runtime_id:
                raise RegistrationError("Runtime registration returned no runtime ID")
            
            self._runtime_id = runtime_id
            self.logger.info(f"Runtime registered successfully with ID: {runtime_id}")
            
            # Update context with runtime ID
            self.context.runtime_id = runtime_id
            
            # TODO: Parse re-registration report from response
            # For now, we'll implement basic registration
            # In next iteration, FAM client will return ReregistrationReport
            
        except Exception as e:
            error_msg = f"Runtime registration failed: {e}"
            self.logger.error(error_msg, exc_info=True)
            raise RegistrationError(error_msg, e)
    
    async def _register_runtime(self) -> str:
        """Register runtime with FAM.
        
        Returns:
            Runtime ID
            
        Raises:
            Exception: If registration fails
        """
        runtime_id = await self._fam_client.register_runtime(
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
            heartbeat_interval=self._runtime_config.get("heartbeat_interval", 6000)
        )
        
        return runtime_id
    
    async def _handle_reregistration_report(
        self,
        report: ReregistrationReport
    ) -> None:
        """Handle re-registration report and trigger recovery.
        
        Args:
            report: Re-registration report from FAM
        """
        self.logger.info("Processing re-registration report")
        
        # Update timestamp storage
        self._timestamp_handler.update_from_report(
            last_registration_time=report.last_registration_time,
            last_heartbeat_time=report.last_heartbeat_time,
            last_metrics_time=report.last_metrics_time,
            last_asset_sync_time=report.last_asset_sync_time
        )
        
        # Check if recovery is needed
        needs_recovery = any([
            report.last_heartbeat_time is not None,
            report.last_metrics_time is not None,
            report.last_asset_sync_time is not None
        ])
        
        if needs_recovery:
            self.logger.info("Recovery needed - triggering recovery tasks")
            
            # Trigger recovery in background
            # (In production, this would be done via task queue or executor)
            recovery_stats = await self._recovery_handler.perform_recovery(
                last_heartbeat_time=report.last_heartbeat_time,
                last_metrics_time=report.last_metrics_time,
                last_asset_sync_time=report.last_asset_sync_time,
                heartbeat_interval=self._runtime_config.get("heartbeat_interval_seconds", 60),
                metrics_interval=self._runtime_config.get("metrics_interval_seconds", 300)
            )
            
            self.logger.info(f"Recovery completed: {recovery_stats}")
        else:
            self.logger.info("No recovery needed - this is first registration")
    
    def get_runtime_id(self) -> Optional[str]:
        """Get the registered runtime ID.
        
        Returns:
            Runtime ID if registration succeeded, None otherwise
        """
        return self._runtime_id


# Made with Bob