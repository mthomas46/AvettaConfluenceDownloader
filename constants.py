import enum

"""
constants.py
------------
Holds all default values, stub values, and user-facing messages for the Confluence Downloader project.
Centralizes configuration and strings for maintainability.
"""

class Mode(enum.Enum):
    """
    Enum for supported download modes.
    """
    ENTIRE_SPACE = '1'
    BY_PARENT_PAGE = '2'

DEFAULT_BASE_URL = "https://avetta.atlassian.net/wiki"
STUB_EMAIL = "your.email@example.com"
STUB_TOKEN = "your-api-token-here"
DEFAULT_OUTPUT_DIR = "confluence_pages"
USER_PROMPT_OVERWRITE = (
    "File '{filepath}' exists. Overwrite? (y/n/a=all/s=skip all/i=increment all) [default: y]: "
)
BATCH_PROMPT = (
    "\nWhat would you like to do when existing files are found?\n"
    "  1. Overwrite all existing files (recommended for most cases).\n"
    "  2. Skip all existing files.\n"
    "  3. Decide for each file interactively.\n"
    "  4. Increment all file names (never overwrite, always create new)"
) 