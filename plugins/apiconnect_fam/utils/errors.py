"""Location: ./plugins/apiconnect_fam/utils/errors.py
Copyright 2026
SPDX-License-Identifier: Apache-2.0
Authors: Shankar N

Custom Exceptions for IBM API Connect FAM Plugin.

Defines a comprehensive exception hierarchy for better error handling,
debugging, and error classification throughout the plugin.

Exception Hierarchy:
    AgentError (base)
    ├── RegistrationError: Runtime registration failures
    ├── RecoveryError: Recovery operation failures
    ├── SyncError: Synchronization failures
    ├── FAMClientError: FAM API client errors
    ├── ValidationError: Configuration/data validation errors
    └── RetryExhaustedError: All retry attempts failed

Usage:
    ```python
    # Raise specific error with cause
    try:
        response = await api_call()
    except httpx.HTTPError as e:
        raise SyncError("Failed to sync servers", cause=e)
    
    # Handle errors with cause chain
    try:
        await sync_operation()
    except SyncError as e:
        logger.error(f"Sync failed: {e}")
        if e.cause:
            logger.error(f"Root cause: {e.cause}")
    
    # Retry exhausted error
    try:
        result = await with_retry(operation)
    except RetryExhaustedError as e:
        logger.error(f"Failed after {e.attempts} attempts")
        logger.error(f"Last error: {e.last_error}")
    ```

Benefits:
    - Clear error classification for different failure types
    - Cause chain preservation for debugging
    - Consistent error handling across the plugin
    - Better error messages and logging

Notes:
    - All exceptions inherit from AgentError for easy catching
    - Cause parameter preserves original exception
    - RetryExhaustedError includes attempt count and last error
    - Use specific exceptions for better error handling
"""


class AgentError(Exception):
    """Base exception for all agent errors."""

    def __init__(self, message: str, cause: Exception = None):
        """Initialize agent error.

        Args:
            message: Error message
            cause: Original exception that caused this error
        """
        super().__init__(message)
        self.cause = cause


class RegistrationError(AgentError):
    """Error during runtime registration."""

    pass


class RecoveryError(AgentError):
    """Error during recovery operations."""

    pass


class SyncError(AgentError):
    """Error during sync operations."""

    pass


class FAMClientError(AgentError):
    """Error in IBM API Connect Federated API Management API client operations."""

    pass


class ValidationError(AgentError):
    """Error in configuration or data validation."""

    pass


class RetryExhaustedError(AgentError):
    """Error when retry attempts are exhausted."""

    def __init__(self, message: str, attempts: int, last_error: Exception):
        """Initialize retry exhausted error.

        Args:
            message: Error message
            attempts: Number of retry attempts made
            last_error: Last error encountered
        """
        super().__init__(message, last_error)
        self.attempts = attempts
        self.last_error = last_error
