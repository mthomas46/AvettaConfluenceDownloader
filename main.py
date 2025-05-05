"""
main.py
-------
Orchestrates the main workflow for the Confluence Downloader project.
Delegates logic to modules (API, file ops, config) and returns results for the CLI to handle output.
No user interaction or printing occurs here.
"""
import sys
from typing import Any
from config import get_env_or_prompt
from confluence_api import (
    get_all_pages_in_space, get_descendants, search_pages_by_title, get_page_id_from_url
)
from file_ops import sanitize_filename, unique_filename, consolidate_markdown_files
from constants import DEFAULT_BASE_URL, STUB_EMAIL, STUB_TOKEN, DEFAULT_OUTPUT_DIR

__version__ = "1.0.0"

def mask_token(token: str) -> str:
    if not token or len(token) < 8:
        return '***'
    return token[:2] + '*' * (len(token) - 6) + token[-4:]

def main(args) -> dict:
    """
    Main workflow. Returns a dict with status and messages for the CLI to handle output.
    """
    dry_run = args.dry_run
    base_url = args.base_url or get_env_or_prompt(
        'CONFLUENCE_BASE_URL',
        'Confluence base URL',
        default=DEFAULT_BASE_URL,
        stub_values=[DEFAULT_BASE_URL, '', None]
    )
    if not base_url.startswith("http://") and not base_url.startswith("https://"):
        base_url = "https://" + base_url

    username = args.username or get_env_or_prompt(
        'CONFLUENCE_USERNAME',
        'Confluence username/email',
        stub_values=[STUB_EMAIL, '', None]
    )
    api_token = get_env_or_prompt(
        'CONFLUENCE_API_TOKEN',
        'Confluence API token',
        is_secret=True,
        stub_values=[STUB_TOKEN, '', None]
    )
    auth = (username, api_token)
    output_dir = args.output_dir or get_env_or_prompt(
        'OUTPUT_DIR',
        'Output directory',
        default=DEFAULT_OUTPUT_DIR,
        stub_values=[DEFAULT_OUTPUT_DIR, '', None]
    )
    # ... rest of workflow, return status/results for CLI to print ...
    return {
        'config': {
            'base_url': base_url,
            'username': username,
            'api_token': mask_token(api_token),
            'output_dir': output_dir,
            'mode': args.mode or 'prompt',
            'metrics_only': args.metrics_only,
            'dry_run': dry_run,
            'verbose': args.verbose,
        },
        'status': 'ok',
        'message': 'Workflow completed (details omitted for brevity)'
    } 