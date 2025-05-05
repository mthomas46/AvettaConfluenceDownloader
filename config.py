"""
config.py
---------
Handles environment variable and user config loading and validation for the Confluence Downloader project.
Provides helpers for prompting and retrieving configuration values.
"""
import os
import getpass
from typing import Optional

def get_env_or_prompt(var: str, prompt: str, default: Optional[str] = None, is_secret: bool = False, stub_values=None) -> str:
    """
    Get a value from the environment or prompt the user if missing or stubbed.
    stub_values: list of values that are considered placeholders and should trigger a prompt.
    """
    value = os.getenv(var)
    if value is not None:
        value = value.strip()
    if not value or (stub_values and value in stub_values):
        if is_secret:
            value = getpass.getpass(f"{prompt}: ").strip()
        else:
            if default:
                value = input(f"{prompt} [default: {default}]: ").strip() or default
            else:
                value = input(f"{prompt}: ").strip()
    return value 