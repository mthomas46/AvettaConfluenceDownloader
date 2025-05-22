"""
error_utils.py
--------------
Error handling utilities for the Confluence Downloader CLI.
Provides a decorator for consistent CLI error handling.
"""
from typing import Callable, Any
from cli_helpers import handle_cli_error

def cli_error_handler(func: Callable) -> Callable:
    """
    Decorator to wrap CLI entry points and helpers for consistent error handling.
    Catches exceptions, reports them, and exits or re-raises as appropriate.
    """
    def wrapper(*args, **kwargs) -> Any:
        try:
            return func(*args, **kwargs)
        except Exception as e:
            handle_cli_error(e)
            # Optionally: exit(1) or re-raise
    return wrapper 