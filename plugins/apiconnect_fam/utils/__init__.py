"""Location: ./plugins/apiconnect_fam/utils/__init__.py
Copyright 2026
SPDX-License-Identifier: Apache-2.0
Authors: Shankar N

Utility Modules for IBM API Connect FAM Plugin.

This package provides common utilities for error handling, retry logic,
and other helper functions used throughout the plugin.

Modules:
    - errors: Custom exception hierarchy for better error handling
    - retry: Retry logic with exponential backoff and circuit breaker

Error Classes:
    - AgentError: Base exception for all plugin errors
    - RegistrationError: Runtime registration failures
    - RecoveryError: Recovery operation failures
    - SyncError: Synchronization operation failures
    - FAMClientError: FAM API client errors
    - ValidationError: Configuration or data validation errors
    - RetryExhaustedError: All retry attempts exhausted

Retry Utilities:
    - RetryConfig: Configuration for retry behavior
    - with_retry: Decorator/wrapper for retry logic
    - exponential_backoff: Calculate backoff delays
    - CircuitBreaker: Circuit breaker pattern implementation

Example:
    ```python
    # Use retry logic
    from contextforge_apiconnect_fam.utils import with_retry, RetryConfig
    
    config = RetryConfig(max_attempts=3, initial_delay=1.0)
    result = await with_retry(
        api_call,
        arg1, arg2,
        retry_config=config,
        operation_name="API Call"
    )
    
    # Handle custom errors
    from contextforge_apiconnect_fam.utils import SyncError
    
    try:
        await sync_operation()
    except SyncError as e:
        logger.error(f"Sync failed: {e}")
        if e.cause:
            logger.error(f"Caused by: {e.cause}")
    ```

Notes:
    - All custom exceptions inherit from AgentError
    - Retry logic supports both sync and async functions
    - Circuit breaker prevents cascading failures
    - Exponential backoff includes jitter to prevent thundering herd
"""

from .errors import (
    AgentError,
    RecoveryError,
    RegistrationError,
    SyncError,
    FAMClientError,
)
from .retry import RetryConfig, with_retry, exponential_backoff

__all__ = [
    "AgentError",
    "RecoveryError",
    "RegistrationError",
    "SyncError",
    "FAMClientError",
    "RetryConfig",
    "with_retry",
    "exponential_backoff",
]
