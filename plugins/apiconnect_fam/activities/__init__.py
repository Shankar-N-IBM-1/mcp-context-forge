"""Location: ./plugins/apiconnect_fam/activities/__init__.py
Copyright 2026
SPDX-License-Identifier: Apache-2.0
Authors: Shankar N

Activity Modules for IBM API Connect FAM Plugin.

This package contains all activity implementations for the plugin.
Activities represent discrete, schedulable operations that run periodically
or on-demand to maintain synchronization with FAM.

Activity Types:
    - Base Activities: Abstract base classes for all activities
    - Registration: Runtime registration with FAM
    - Heartbeat: Periodic status updates to FAM
    - Metrics: Performance metrics collection and reporting
    - Sync Activities: Server and tool synchronization

Available Activities:
    - AbstractActivity: Base class for all activities
    - AbstractScheduledActivity: Base class for scheduled activities
    - RegisterRuntimeActivity: Registers runtime with FAM (one-time)
    - SendHeartbeatActivity: Sends periodic heartbeats (scheduled)
    - SendMetricsActivity: Collects and sends metrics (scheduled)
    - SyncServersActivity: Synchronizes MCP servers (scheduled)
    - SyncToolsActivity: Synchronizes MCP tools (scheduled)

Activity Lifecycle:
    1. Initialize: Create activity with context and configuration
    2. Execute: Run activity logic with error handling
    3. Perform: Actual work done by the activity (implemented by subclass)

Example:
    ```python
    # Create and execute an activity
    context = ActivityContext(runtime_id="my-runtime", ...)
    activity = SendHeartbeatActivity(context, fam_client, interval=60)
    success = await activity.execute()
    ```

Notes:
    - All activities inherit from AbstractActivity or AbstractScheduledActivity
    - Scheduled activities run at fixed intervals
    - Activities include built-in error handling and logging
    - State tracking prevents redundant operations
"""

# Local
from .base import AbstractActivity, AbstractScheduledActivity
from .register_runtime import RegisterRuntimeActivity
from .send_heartbeat import SendHeartbeatActivity
from .send_metrics import SendMetricsActivity
from .sync_servers import SyncServersActivity
from .sync_tools import SyncToolsActivity

__all__ = [
    "AbstractActivity",
    "AbstractScheduledActivity",
    "RegisterRuntimeActivity",
    "SendHeartbeatActivity",
    "SendMetricsActivity",
    "SyncServersActivity",
    "SyncToolsActivity",
]
