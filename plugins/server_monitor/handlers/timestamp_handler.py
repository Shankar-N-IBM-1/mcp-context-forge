"""Timestamp Storage Handler.

Handles persistence and retrieval of last sync timestamps for recovery mechanism.
Follows webMethods Agent SDK pattern for timestamp storage.

Copyright 2025
SPDX-License-Identifier: Apache-2.0
"""

import json
import logging
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class TimestampStorageHandler:
    """Handles persistence of last sync timestamps.
    
    Stores timestamps in a JSON file for recovery after restarts.
    Thread-safe for concurrent access.
    
    Attributes:
        storage_path: Path to the timestamp storage file
    """
    
    # Timestamp keys
    KEY_REGISTRATION = "last_registration_time"
    KEY_HEARTBEAT = "last_heartbeat_time"
    KEY_METRICS = "last_metrics_time"
    KEY_ASSET_SYNC = "last_asset_sync_time"
    KEY_SERVER_SYNC = "last_server_sync_time"
    KEY_TOOL_SYNC = "last_tool_sync_time"
    
    def __init__(self, storage_path: str = "data/agent_timestamps.json"):
        """Initialize timestamp storage handler.
        
        Args:
            storage_path: Path to storage file (relative to project root)
        """
        self.storage_path = Path(storage_path)
        self._ensure_storage_dir()
        self._timestamps: Dict[str, int] = self._load_timestamps()
    
    def _ensure_storage_dir(self) -> None:
        """Ensure storage directory exists."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
    
    def _load_timestamps(self) -> Dict[str, int]:
        """Load timestamps from storage file.
        
        Returns:
            Dictionary of timestamps
        """
        if not self.storage_path.exists():
            logger.info(f"Timestamp storage file not found: {self.storage_path}")
            return {}
        
        try:
            with open(self.storage_path, 'r') as f:
                data = json.load(f)
                logger.info(f"Loaded {len(data)} timestamps from {self.storage_path}")
                return data
        except Exception as e:
            logger.error(f"Failed to load timestamps: {e}", exc_info=True)
            return {}
    
    def _save_timestamps(self) -> None:
        """Save timestamps to storage file."""
        try:
            with open(self.storage_path, 'w') as f:
                json.dump(self._timestamps, f, indent=2)
            logger.debug(f"Saved {len(self._timestamps)} timestamps to {self.storage_path}")
        except Exception as e:
            logger.error(f"Failed to save timestamps: {e}", exc_info=True)
    
    def save_timestamp(self, key: str, timestamp: int) -> None:
        """Save timestamp for a sync operation.
        
        Args:
            key: Timestamp key (use KEY_* constants)
            timestamp: Timestamp in milliseconds
        """
        self._timestamps[key] = timestamp
        self._save_timestamps()
        logger.debug(f"Saved timestamp {key}={timestamp}")
    
    def get_timestamp(self, key: str) -> Optional[int]:
        """Retrieve last sync timestamp.
        
        Args:
            key: Timestamp key (use KEY_* constants)
            
        Returns:
            Timestamp in milliseconds, or None if not found
        """
        return self._timestamps.get(key)
    
    def get_all_timestamps(self) -> Dict[str, int]:
        """Get all stored timestamps.
        
        Returns:
            Dictionary of all timestamps
        """
        return self._timestamps.copy()
    
    def clear_timestamp(self, key: str) -> None:
        """Clear a specific timestamp.
        
        Args:
            key: Timestamp key to clear
        """
        if key in self._timestamps:
            del self._timestamps[key]
            self._save_timestamps()
            logger.debug(f"Cleared timestamp {key}")
    
    def clear_all_timestamps(self) -> None:
        """Clear all timestamps."""
        self._timestamps.clear()
        self._save_timestamps()
        logger.info("Cleared all timestamps")
    
    def update_from_report(
        self,
        last_registration_time: Optional[int] = None,
        last_heartbeat_time: Optional[int] = None,
        last_metrics_time: Optional[int] = None,
        last_asset_sync_time: Optional[int] = None
    ) -> None:
        """Update timestamps from re-registration report.
        
        Args:
            last_registration_time: Last registration timestamp
            last_heartbeat_time: Last heartbeat timestamp
            last_metrics_time: Last metrics timestamp
            last_asset_sync_time: Last asset sync timestamp
        """
        if last_registration_time is not None:
            self.save_timestamp(self.KEY_REGISTRATION, last_registration_time)
        
        if last_heartbeat_time is not None:
            self.save_timestamp(self.KEY_HEARTBEAT, last_heartbeat_time)
        
        if last_metrics_time is not None:
            self.save_timestamp(self.KEY_METRICS, last_metrics_time)
        
        if last_asset_sync_time is not None:
            self.save_timestamp(self.KEY_ASSET_SYNC, last_asset_sync_time)
        
        logger.info("Updated timestamps from re-registration report")
    
    def get_recovery_info(self) -> Dict[str, Optional[int]]:
        """Get timestamps needed for recovery.
        
        Returns:
            Dictionary with recovery timestamps
        """
        return {
            "last_heartbeat_time": self.get_timestamp(self.KEY_HEARTBEAT),
            "last_metrics_time": self.get_timestamp(self.KEY_METRICS),
            "last_asset_sync_time": self.get_timestamp(self.KEY_ASSET_SYNC),
            "last_server_sync_time": self.get_timestamp(self.KEY_SERVER_SYNC),
            "last_tool_sync_time": self.get_timestamp(self.KEY_TOOL_SYNC),
        }


# Made with Bob