"""Sync Orchestrator Module.

Coordinates all synchronization tasks (servers, tools, metrics) with FAM.

Copyright 2025
SPDX-License-Identifier: Apache-2.0
"""

import asyncio
import logging
from typing import Optional

from mcpgateway.db import Server, SessionLocal

from .fam_client import FAMAssetCatalogClient
from .server_sync import ServerSyncTask
from .tool_sync import ToolSyncTask
from .metrics_sync import MetricsSyncTask
from .heartbeat_sync import HeartbeatSyncTask

logger = logging.getLogger(__name__)


class SyncOrchestrator:
    """Orchestrates all synchronization tasks.
    
    Manages:
    - Server synchronization
    - Tool synchronization
    - Metrics synchronization
    - Runtime heartbeat
    - Logging and statistics
    
    Runs tasks on a configurable interval and coordinates their execution.
    """
    
    def __init__(
        self,
        fam_client: FAMAssetCatalogClient,
        runtime_id: str,
        interval_seconds: int = 60,
        log_details: bool = True,
        metrics_sync_enabled: bool = False,
        metrics_sync_interval: int = 300,
        heartbeat_enabled: bool = True,
        heartbeat_interval: int = 60
    ):
        """Initialize sync orchestrator.
        
        Args:
            fam_client: FAM API client
            runtime_id: Runtime ID for heartbeat
            interval_seconds: How often to run sync tasks (in seconds)
            log_details: Whether to log detailed server information
            metrics_sync_enabled: Whether to enable metrics synchronization
            metrics_sync_interval: How often to sync metrics (in seconds). Also used as time window for metrics collection.
            heartbeat_enabled: Whether to enable runtime heartbeat
            heartbeat_interval: How often to send heartbeats (in seconds)
        """
        self._fam_client = fam_client
        self._runtime_id = runtime_id
        self._interval_seconds = interval_seconds
        self._log_details = log_details
        
        # Initialize sync tasks
        self._server_sync = ServerSyncTask(fam_client)
        self._tool_sync = ToolSyncTask(fam_client)
        
        # Initialize metrics sync if enabled
        self._metrics_sync: Optional[MetricsSyncTask] = None
        if metrics_sync_enabled:
            self._metrics_sync = MetricsSyncTask(
                fam_client,
                sync_interval=metrics_sync_interval
            )
        
        # Initialize heartbeat sync if enabled
        self._heartbeat_sync: Optional[HeartbeatSyncTask] = None
        if heartbeat_enabled:
            self._heartbeat_sync = HeartbeatSyncTask(
                fam_client,
                runtime_id=runtime_id,
                heartbeat_interval=heartbeat_interval
            )
        
        # Task management
        self._task: Optional[asyncio.Task] = None
        self._running = False
    
    async def start(self) -> None:
        """Start the orchestrator background task."""
        logger.info(f"Starting SyncOrchestrator with interval={self._interval_seconds}s")
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
    
    async def stop(self) -> None:
        """Stop the orchestrator background task."""
        logger.info("Stopping SyncOrchestrator")
        self._running = False
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
    
    async def _run_loop(self) -> None:
        """Main orchestrator loop that runs sync tasks periodically."""
        while self._running:
            try:
                await self._execute_sync_cycle()
            except Exception as e:
                logger.error(f"Error in sync orchestrator loop: {e}", exc_info=True)
            
            # Wait for the configured interval
            try:
                await asyncio.sleep(self._interval_seconds)
            except asyncio.CancelledError:
                break
    
    async def _execute_sync_cycle(self) -> None:
        """Execute one complete sync cycle.
        
        Runs all enabled sync tasks and logs summary information.
        """
        try:
            # Execute server sync
            await self._server_sync.execute()
            
            # Execute tool sync
            await self._tool_sync.execute()
            
            # Execute metrics sync if enabled
            if self._metrics_sync:
                await self._metrics_sync.execute()
            
            # Execute heartbeat sync if enabled
            if self._heartbeat_sync:
                await self._heartbeat_sync.execute()
            
            # Log summary information
            await self._log_summary()
            
        except Exception as e:
            logger.error(f"Error in sync cycle: {e}", exc_info=True)
    
    async def _log_summary(self) -> None:
        """Log summary information about servers and sync status."""
        try:
            with SessionLocal() as db:
                servers = db.query(Server).all()
                
                # Log server summary
                server_count = len(servers)
                enabled_count = sum(1 for s in servers if s.enabled)
                disabled_count = server_count - enabled_count
                
                logger.info(
                    f"Virtual Servers Summary: Total={server_count}, "
                    f"Enabled={enabled_count}, Disabled={disabled_count}"
                )
                
                # Log detailed server information if enabled
                if self._log_details and servers:
                    self._log_server_details(servers)
                
                # Log sync statistics
                self._log_sync_stats()
                
        except Exception as e:
            logger.error(f"Error logging summary: {e}", exc_info=True)
    
    def _log_server_details(self, servers: list) -> None:
        """Log detailed information for each server.
        
        Args:
            servers: List of Server ORM objects
        """
        logger.info("=" * 80)
        
        for server in servers:
            status = "ENABLED" if server.enabled else "DISABLED"
            logger.info(f"  [{status}] {server.name} (ID: {server.id})")
            
            if server.description:
                logger.info(f"    Description: {server.description}")
            
            logger.info(f"    Created: {server.created_at}")
            
            if server.tags:
                logger.info(f"    Tags: {', '.join(server.tags)}")
            
            # Log associated items count
            tool_count = len(server.tools) if server.tools else 0
            resource_count = len(server.resources) if server.resources else 0
            prompt_count = len(server.prompts) if server.prompts else 0
            
            logger.info(
                f"    Associated Items: Tools={tool_count}, "
                f"Resources={resource_count}, Prompts={prompt_count}"
            )
            logger.info("")
        
        logger.info("=" * 80)
    
    def _log_sync_stats(self) -> None:
        """Log synchronization statistics from all tasks."""
        server_stats = self._server_sync.get_stats()
        tool_stats = self._tool_sync.get_stats()
        
        logger.info(
            f"Sync Stats - Servers: {server_stats['synced_servers']}, "
            f"Tools: {tool_stats['synced_tools']}"
        )
        
        if self._metrics_sync:
            metrics_stats = self._metrics_sync.get_stats()
            logger.info(
                f"Metrics Sync - Count: {metrics_stats['sync_count']}, "
                f"Last: {metrics_stats['last_sync']}, "
                f"Interval: {metrics_stats['sync_interval']}s"
            )
    
    def get_stats(self) -> dict:
        """Get comprehensive statistics from all sync tasks.
        
        Returns:
            Dict with statistics from all tasks
        """
        stats = {
            "server_sync": self._server_sync.get_stats(),
            "tool_sync": self._tool_sync.get_stats(),
            "interval_seconds": self._interval_seconds,
            "running": self._running,
            "runtime_id": self._runtime_id
        }
        
        if self._metrics_sync:
            stats["metrics_sync"] = self._metrics_sync.get_stats()
        
        if self._heartbeat_sync:
            stats["heartbeat_sync"] = self._heartbeat_sync.get_stats()
        
        return stats

# Made with Bob
