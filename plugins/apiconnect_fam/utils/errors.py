"""Custom Exceptions for Server Monitor Plugin.

Defines exception hierarchy for better error handling and debugging.

Copyright 2025
SPDX-License-Identifier: Apache-2.0
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
    """Error in FAM API client operations."""
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


# Made with Bob