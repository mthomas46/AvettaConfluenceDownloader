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
from file_ops import sanitize_filename, unique_filename, consolidate_markdown_files, save_page, build_page_filepath
from constants import DEFAULT_BASE_URL, STUB_EMAIL, STUB_TOKEN, DEFAULT_OUTPUT_DIR, Mode
import os
from tqdm import tqdm
import time
from itertools import cycle

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
    # Gather configuration from CLI args, environment, or prompt
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
        print("[Progress] Extracting page ID from parent URL...")
        parent_id = get_page_id_from_url(parent_url, base_url, auth)
        if not parent_id:
            return {
                'config': locals(),
                'status': 'error',
                'message': 'Could not extract page ID from parent URL.'
            }
        print("[Progress] Fetching all descendant pages from Confluence (this may take a while)...")
        # Spinner for API call
        import threading
        stop_spinner = False
        def spinner():
            for c in cycle(['|', '/', '-', '\\']):
                if stop_spinner:
                    break
                print(f'\r[Progress] Fetching pages... {c}', end='', flush=True)
                time.sleep(0.1)
            print('\r', end='', flush=True)
        spinner_thread = threading.Thread(target=spinner)
        spinner_thread.start()
        pages = get_descendants(base_url, auth, parent_id)
        stop_spinner = True
        spinner_thread.join()
        print("[Progress] Finished fetching descendant pages.")
        if not pages:
            return {
                'config': locals(),
                'status': 'error',
                'message': 'No pages found under the specified parent page. Check permissions or the URL.'
            }
        parent_title = pages[0].get('title') if pages else None
        from file_ops import consolidate_markdown_files  # avoid circular import
        from datetime import datetime
        from file_ops import sanitize_filename
        # Write metrics report if available
        try:
            from confluence_downloader import write_metrics_md
        except ImportError:
            write_metrics_md = None
        if write_metrics_md:
            write_metrics_md(pages, output_dir, mode_enum.value, parent_title)
        downloaded_files = []
        # Save pages as Markdown unless metrics_only; collect filenames for reporting
        if not args.metrics_only:
            print("[Progress] Saving downloaded pages as Markdown files...")
            for page_index in range(len(pages)):
                page = pages[page_index]
                dir_path, filename, file_path = build_page_filepath(page, output_dir)
                save_success = save_page(
                    page,
                    output_dir,
                    overwrite_mode=getattr(args, 'overwrite_mode', 'overwrite'),
                    dry_run=dry_run
                )
                if save_success:
                    downloaded_files.append(file_path)
                else:
                    print(f"[Progress] Error saving page: {page.get('title', 'Untitled')}")
                    return {
                        'config': locals(),
                        'status': 'error',
                        'message': f'Error saving page "{page.get('title', 'Untitled')}".'
                    }
            print("[Progress] Finished saving all pages.")
        # Return summary, config, and file list for CLI to display
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
                'overwrite_mode': getattr(args, 'overwrite_mode', 'overwrite'),
                'parent_url': parent_url,
            },
            'status': 'ok',
            'message': f"Downloaded and saved {len(downloaded_files)} pages under parent '{parent_title}'. Metrics written to {output_dir}/metrics.md.",
            'downloaded_files': downloaded_files,
            'selected_options': {
                'mode': mode_enum.value,
                'parent_url': parent_url,
                'dry_run': dry_run,
                'overwrite_mode': getattr(args, 'overwrite_mode', 'overwrite'),
                'metrics_only': args.metrics_only,
                'output_dir': output_dir,
                'verbose': args.verbose,
            }
        }
    else:
        # Only mode 2 (by parent) is implemented in this workflow
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