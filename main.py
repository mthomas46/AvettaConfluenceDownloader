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
from constants import DEFAULT_BASE_URL, STUB_EMAIL, STUB_TOKEN, DEFAULT_OUTPUT_DIR, Mode
import os

__version__ = "1.0.0"

def mask_token(token: str) -> str:
    """
    Mask the API token for display/logging.
    Args:
        token (str): The API token.
    Returns:
        str: Masked token.
    """
    if not token or len(token) < 8:
        return '***'
    return token[:2] + '*' * (len(token) - 6) + token[-4:]

def main(args) -> dict:
    """
    Main workflow. Returns a dict with status and messages for the CLI to handle output.
    Args:
        args (argparse.Namespace): Parsed CLI arguments.
    Returns:
        dict: Status, config, and message for CLI output.
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

    mode = args.mode or 'prompt'
    if mode in (Mode.ENTIRE_SPACE.value, Mode.BY_PARENT_PAGE.value):
        mode_enum = Mode(mode)
    else:
        mode_enum = None

    # Only implement 'by parent' mode workflow
    if mode_enum == Mode.BY_PARENT_PAGE:
        parent_url = args.parent_url
        if not parent_url:
            return {
                'config': locals(),
                'status': 'error',
                'message': 'Parent page URL is required for mode 2 (by parent).'
            }
        parent_id = get_page_id_from_url(parent_url, base_url, auth)
        if not parent_id:
            return {
                'config': locals(),
                'status': 'error',
                'message': 'Could not extract page ID from parent URL.'
            }
        pages = get_descendants(base_url, auth, parent_id)
        if not pages:
            return {
                'config': locals(),
                'status': 'error',
                'message': 'No pages found under the specified parent page. Check permissions or the URL.'
            }
        parent_title = pages[0].get('title') if pages else None
        # Write metrics report
        from file_ops import consolidate_markdown_files  # avoid circular import
        from datetime import datetime
        from file_ops import sanitize_filename
        # Write metrics report (reuse or implement write_metrics_md if available)
        try:
            from confluence_downloader import write_metrics_md
        except ImportError:
            write_metrics_md = None
        if write_metrics_md:
            write_metrics_md(pages, output_dir, mode_enum.value, parent_title)
        # Save pages as Markdown unless metrics_only or dry_run
        if not args.metrics_only and not dry_run:
            for page in pages:
                title = page.get('title', 'Untitled')
                ancestors = page.get('ancestors', [])
                path_parts = [sanitize_filename(a.get('title', '')) for a in ancestors if a.get('title')]
                dir_path = os.path.join(output_dir, *path_parts) if path_parts else output_dir
                filename = sanitize_filename(title) + ".md"
                filepath = os.path.join(dir_path, filename)
                os.makedirs(dir_path, exist_ok=True)
                storage_val = page.get('body', {}).get('storage', {}).get('value', '')
                from file_ops import confluence_storage_to_markdown
                markdown = confluence_storage_to_markdown(storage_val)
                try:
                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(markdown)
                except Exception as e:
                    return {
                        'config': locals(),
                        'status': 'error',
                        'message': f'Error saving page "{title}": {e}'
                    }
        return {
            'config': {
                'base_url': base_url,
                'username': username,
                'api_token': mask_token(api_token),
                'output_dir': output_dir,
                'mode': mode_enum.value,
                'metrics_only': args.metrics_only,
                'dry_run': dry_run,
                'verbose': args.verbose,
            },
            'status': 'ok',
            'message': f"Downloaded and saved {len(pages)} pages under parent '{parent_title}'. Metrics written to {output_dir}/metrics.md."
        }
    else:
        return {
            'config': {
                'base_url': base_url,
                'username': username,
                'api_token': mask_token(api_token),
                'output_dir': output_dir,
                'mode': mode_enum.value if mode_enum else mode,
                'metrics_only': args.metrics_only,
                'dry_run': dry_run,
                'verbose': args.verbose,
            },
            'status': 'error',
            'message': 'Only mode 2 (by parent) is implemented in this workflow.'
        } 