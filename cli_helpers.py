"""
cli_helpers.py
-------------
Helper functions for CLI prompts, reporting, and user interaction for the Confluence Downloader project.
Includes prompt helpers, output/reporting helpers, and stubs for error handling and logging utilities.

All prompt logic, including prompt_with_validation, lives here to avoid circular imports.
"""
from colorama import Fore, Style
from typing import Any, Dict, Optional
from constants import BATCH_PROMPT
# from cli import prompt_with_validation  # Removed to avoid circular import
import questionary
from yaspin import yaspin
from confluence_api import get_all_spaces, process_space_with_llm_cache, generate_redundancy_similarity_report, generate_coverage_heatmap, check_llm_server_health
import os
from tqdm import tqdm
import re
from tabulate import tabulate
import json
import sys
import subprocess
import logging
import time
import requests
from datetime import datetime
import tempfile
from bs4 import BeautifulSoup
import shutil
from file_ops import confluence_storage_to_markdown
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed

# Setup CLI logging
logger = logging.getLogger("cli_helpers")
if not logger.hasHandlers():
    handler = logging.FileHandler("cli_helpers.log")
    formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

def prompt_use_yaml_config() -> Optional[str]:
    """
    Prompt the user at the start to choose whether to run from a YAML config file or proceed interactively.
    Returns the path to the YAML config file if chosen, otherwise None.
    """
    print(f"{Fore.CYAN}\n=== Configuration Source Selection ==={Style.RESET_ALL}")
    use_yaml = prompt_with_validation(
        f"{Fore.YELLOW}Would you like to load options from a YAML config file?{Style.RESET_ALL}",
        valid_options=['Yes', 'No'],
        default='No'
    )
    if use_yaml == 'Yes':
        config_path = input(f"{Fore.YELLOW}Enter path to YAML config file [default: config.yaml]: {Style.RESET_ALL}").strip()
        return config_path or 'config.yaml'
    return None

def prompt_mode(args) -> None:
    """Prompt the user for download mode if not already set."""
    if not args.mode:
        print(f"{Fore.CYAN}\n=== Download Mode Selection ===\n{Style.RESET_ALL}")
        mode_choice = prompt_with_validation(
            f"{Fore.YELLOW}Select download mode:{Style.RESET_ALL}",
            valid_options=['Download entire space', 'Download by parent page'],
            default='Download by parent page'
        )
        args.mode = '1' if mode_choice == 'Download entire space' else '2'

def prompt_parent_url(args) -> None:
    """Prompt the user for parent URL if needed for mode 2."""
    if args.mode == '2' and not args.parent_url:
        print(f"{Fore.CYAN}\n=== Parent Page Selection ===\n{Style.RESET_ALL}")
        default_parent_url = "https://avetta.atlassian.net/wiki/spaces/it/pages/1122336779"
        entered_url = input(f"{Fore.YELLOW}Enter parent page URL\n[default: {default_parent_url}]: {Style.RESET_ALL}").strip()
        args.parent_url = entered_url or default_parent_url

def prompt_dry_run(args) -> None:
    """Prompt the user for dry run mode if not already set."""
    if args.dry_run is None:
        print(f"{Fore.CYAN}\n=== Dry Run Option ===\n{Style.RESET_ALL}")
        dry_run_choice = prompt_with_validation(
            f"{Fore.YELLOW}Run in dry run mode? (no files will be written){Style.RESET_ALL}",
            valid_options=['Yes', 'No'],
            default='No'
        )
        args.dry_run = (dry_run_choice == 'Yes')

def prompt_file_overwrite_mode(args) -> None:
    """Prompt the user for file download overwrite mode."""
    if not args.dry_run and not args.metrics_only:
        print(f"{Fore.CYAN}\n=== Overwrite Options for File Downloads ===\n{Style.RESET_ALL}")
        overwrite_choice = prompt_with_validation(
            f"{Fore.YELLOW}{BATCH_PROMPT}{Style.RESET_ALL}",
            valid_options=['Overwrite all existing files', 'Skip all existing files', 'Decide for each file interactively', 'Increment all file names'],
            default='Overwrite all existing files'
        )
        overwrite_map = {
            'Overwrite all existing files': 'overwrite',
            'Skip all existing files': 'skip',
            'Decide for each file interactively': 'ask',
            'Increment all file names': 'increment'
        }
        args.overwrite_mode = overwrite_map[overwrite_choice]
    else:
        args.overwrite_mode = 'overwrite'

def prompt_llm_combine(args) -> None:
    """Prompt the user for LLM combine option if not already set."""
    if not getattr(args, 'llm_combine', False):
        print(f"\n{Fore.CYAN}=== LLM Combine Option ==={Style.RESET_ALL}")
        llm_combine_choice = prompt_with_validation(
            f"{Fore.YELLOW}Combine downloaded files into one using an LLM?{Style.RESET_ALL}",
            valid_options=['Yes', 'No'],
            default='No'
        )
        args.llm_combine = (llm_combine_choice == 'Yes')

def prompt_llm_overwrite_mode(args) -> None:
    """Prompt the user for LLM combine overwrite mode if not already set."""
    if not hasattr(args, 'llm_overwrite_mode') or args.llm_overwrite_mode is None:
        print(f"{Fore.CYAN}\n=== Overwrite Options for LLM Combined File ===\n{Style.RESET_ALL}")
        llm_overwrite_choice = prompt_with_validation(
            f"{Fore.YELLOW}How should the LLM combined file be saved if a file with the same name exists?{Style.RESET_ALL}",
            valid_options=['Overwrite the existing combined file', 'Increment the filename'],
            default='Overwrite the existing combined file'
        )
        llm_overwrite_map = {
            'Overwrite the existing combined file': 'overwrite',
            'Increment the filename': 'increment'
        }
        args.llm_overwrite_mode = llm_overwrite_map[llm_overwrite_choice]

def prompt_llm_model(args) -> None:
    """Prompt the user for LLM model selection if not already set."""
    if getattr(args, 'llm_combine', False) and not getattr(args, 'llm_model', None):
        print(f"\n{Fore.CYAN}=== LLM Model Selection ==={Style.RESET_ALL}")
        llm_model_choice = prompt_with_validation(
            f"{Fore.YELLOW}Select LLM model for combining files:{Style.RESET_ALL}",
            valid_options=[
                'gpt-3.5-turbo (free)',
                'gpt-4.1 (gpt-4-1106-preview, NOT free)',
                'gpt-4o (NOT free)',
                'claude-3.5-sonnet (NOT free, Anthropic API key required)'
            ],
            default='gpt-3.5-turbo (free)'
        )
        llm_model_map = {
            'gpt-3.5-turbo (free)': 'gpt-3.5-turbo',
            'gpt-4.1 (gpt-4-1106-preview, NOT free)': 'gpt-4-1106-preview',
            'gpt-4o (NOT free)': 'gpt-4o',
            'claude-3.5-sonnet (NOT free, Anthropic API key required)': 'claude-3.5-sonnet'
        }
        args.llm_model = llm_model_map[llm_model_choice]

def prompt_llm_prompt_style(args, llm_model: str, llm_free_prompt_mode: Optional[str]) -> str:
    """Prompt the user for LLM prompt style if using a free model and not already set."""
    paid_models = ["gpt-4", "gpt-4-turbo", "gpt-4-32k", "gpt-4o", "gpt-4-1106-preview"]
    if (llm_model or 'gpt-3.5-turbo') not in paid_models and not llm_free_prompt_mode:
        print(f"\n{Fore.CYAN}=== LLM Free Prompt Selection ==={Style.RESET_ALL}")
        print(f"{Fore.YELLOW}Choose the prompt style for the free LLM model:{Style.RESET_ALL}")
        print(f"  1. Default (detailed, organized, with AI note and formatting guide)")
        print(f"  2. Quick (short, direct: 'combine these files into 1. preserve all unique information. improve readability and flow. create sections and reorder information based on need and where applicable')")
        prompt_choice = prompt_with_validation(
            f"{Fore.YELLOW}Enter 1 for Default, 2 for Quick [default: 1]:{Style.RESET_ALL}",
            valid_options=['1', '2'],
            default='1'
        )
        return "quick" if prompt_choice == '2' else "default"
    return llm_free_prompt_mode or "default"

def prompt_advanced_options(args) -> None:
    print(f"{Fore.CYAN}\n=== Advanced Options ===\n{Style.RESET_ALL}")
    if getattr(args, 'metrics_only', None) is None:
        metrics_choice = prompt_with_validation(
            f"{Fore.YELLOW}Enable metrics-only mode? (no files will be downloaded, only a metrics report will be generated){Style.RESET_ALL}",
            valid_options=['Yes', 'No'],
            default='No'
        )
        args.metrics_only = (metrics_choice == 'Yes')
    if getattr(args, 'verbose', None) is None:
        verbose_choice = prompt_with_validation(
            f"{Fore.YELLOW}Enable verbose logging?{Style.RESET_ALL}",
            valid_options=['Yes', 'No'],
            default='No'
        )
        args.verbose = (verbose_choice == 'Yes')

def print_summary(args) -> None:
    """Print a summary of selected options before execution."""
    print(f"{Fore.CYAN}\n=== Summary of Selected Options ==={Style.RESET_ALL}")
    print(f"  Mode: {args.mode}")
    if args.mode == '2':
        print(f"  Parent URL: {args.parent_url}")
    print(f"  Dry Run: {args.dry_run}")
    print(f"  Overwrite Mode (File Downloads): {args.overwrite_mode}")
    print(f"  Overwrite Mode (LLM Combine): {getattr(args, 'llm_overwrite_mode', None)}")
    print(f"  Metrics Only: {args.metrics_only}")
    print(f"  Output Directory: {args.output_dir or 'confluence_pages'}")
    print(f"  Verbose: {args.verbose}")

def print_config_report(result: Dict[str, Any], args) -> None:
    """Print the configuration report after execution."""
    config_lines = ["\nConfiguration:"]
    for option_name, option_value in result['config'].items():
        config_lines.append(f"  {option_name}: {option_value}")
    if 'overwrite_mode' in result['config']:
        config_lines.append(f"  Overwrite Mode (File Downloads): {result['config'].get('overwrite_mode')}")
    if hasattr(args, 'llm_overwrite_mode'):
        config_lines.append(f"  Overwrite Mode (LLM Combine): {getattr(args, 'llm_overwrite_mode')}")
    config_lines.append(f"\nStatus: {result['status']}")
    config_lines.append(result['message'])
    print('\n'.join(config_lines))

def print_selected_options(result: Dict[str, Any]) -> None:
    """Print the selected options after execution."""
    if 'selected_options' in result:
        selected_lines = [f"\n{Fore.CYAN}=== Selected Options ==={Style.RESET_ALL}"]
        for option_name, option_value in result['selected_options'].items():
            selected_lines.append(f"  {option_name}: {option_value}")
        print('\n'.join(selected_lines))

def print_downloaded_files(result: Dict[str, Any]) -> None:
    """Print the list of downloaded files after execution."""
    if 'downloaded_files' in result:
        if result['downloaded_files']:
            files_section = [f"\n{Fore.CYAN}=== Downloaded Files ==={Style.RESET_ALL}"]
            files_section += [f"  {file_path}" for file_path in result['downloaded_files']]
            print('\n'.join(files_section))
        else:
            print(f"\n{Fore.CYAN}=== Downloaded Files ==={Style.RESET_ALL}\n  (No files were downloaded.)")

def print_llm_combine_status(llm_output_path: Optional[str], logger) -> None:
    """Print the status of the LLM combine operation."""
    if llm_output_path:
        print(f"{Fore.GREEN}LLM-combined file saved to: {llm_output_path}{Style.RESET_ALL}")
        logger.info(f"LLM-combined file saved to: {llm_output_path}")
    else:
        print(f"{Fore.RED}LLM combine failed. See logs for details.{Style.RESET_ALL}")
        logger.error("LLM combine failed. No output file was created.")

# Stub for error handling utilities (to be implemented)
def handle_cli_error(error: Exception) -> None:
    """Handle and report CLI errors in a consistent way."""
    print(f"{Fore.RED}Error: {error}{Style.RESET_ALL}")
    # Optionally log or re-raise

# Stub for logging setup (to be implemented)
def setup_cli_logging(verbose: bool = False) -> None:
    """Set up logging for the CLI."""
    pass

# Section header
def print_section(title):
    print(f"{Fore.CYAN}\n=== {title} ==={Style.RESET_ALL}")

# Main menu
def main_menu():
    print_section("Main Menu")
    return questionary.select(
        "What would you like to do?",
        choices=[
            {"name": "Start API Server", "value": "start_api_server"},
            {"name": "Stop API Server", "value": "stop_api_server"},
            {"name": "Start LLM Server", "value": "start_llm_server"},
            {"name": "Stop LLM Server", "value": "stop_llm_server"},
            {"name": "Test API Server", "value": "test_api_server"},
            {"name": "Test LLM Server", "value": "test_llm_server"},
            {"name": "View API Server Logs", "value": "view_api_server_logs"},
            {"name": "View LLM Server Logs", "value": "view_llm_server_logs"},
            {"name": "Analyze Server Logs", "value": "analyze_server_logs"},
            {"name": "Crawl all spaces", "value": "__ALL__"},
            {"name": "Process LLM Cache for a Space", "value": "llm_cache_space"},
            {"name": "Process LLM Cache for All Spaces", "value": "llm_cache_all"},
            {"name": "Run LLM Cache Process (Advanced)", "value": "llm_cache_advanced"},
            {"name": "Generate Redundancy Report", "value": "redundancy_report"},
            {"name": "Generate Coverage Heatmap", "value": "coverage_heatmap"},
            {"name": "Search/Analyze LLM Metadata", "value": "llm_search_analytics"},
            "Search by title",
            "Generate space structure report",
            {"name": "⬅️  Back", "value": "__BACK__"},
            {"name": "❌ Abort", "value": "__ABORT__"},
            "Exit"
        ]
    ).ask()

# Mode selection
def select_mode():
    print_section("Mode Selection")
    return questionary.select(
        "Select mode:",
        choices=[
            {"name": "Crawl all spaces", "value": '__ALL__'},
            {"name": "Search by title", "value": '3'},
            {"name": "Generate space structure report", "value": '4'}
        ]
    ).ask()

# Spinner context manager
def spinner(text):
    return yaspin(text=text, color="cyan")

# Prompt with validation
def prompt_with_validation(prompt, valid_options=None, default=None, allow_blank=False):
    if valid_options:
        return questionary.select(
            prompt,
            choices=valid_options,
            default=default if default in valid_options else None
        ).ask()
    else:
        while True:
            user_input = input(f"{prompt}: ").strip()
            if allow_blank and user_input == '':
                return user_input
            if user_input or default is not None:
                return user_input or default

def prompt_space_key(base_url, auth) -> str:
    """Prompt the user to select a Confluence space key from a cached, fuzzy-searchable list. Includes Back/Abort options."""
    print_section("Confluence Space Selection")
    spaces = get_all_spaces(base_url, auth)
    print(f"[DEBUG] Loaded {len(spaces)} spaces for prompt: {spaces[:5]}")
    # Filter out personal spaces (keys starting with ~)
    spaces = [s for s in spaces if not s['key'].startswith('~')]
    # Sort spaces by name, then key
    spaces = sorted(spaces, key=lambda s: (s['name'].lower(), s['key'].lower()))
    print(f"[DEBUG] Filtered to {len(spaces)} non-personal spaces for prompt: {spaces[:5]}")
    if not spaces:
        print(f"{Fore.RED}No spaces found or failed to fetch spaces.{Style.RESET_ALL}")
        return None
    display_map = {f"{s['key']} - {s['name']}": s['key'] for s in spaces}
    display_choices = list(display_map.keys())
    prompt_text = (
        "Select a Confluence space (type to search, list from cache; delete cache/spaces.json to refresh):"
    )
    # Add Back/Abort options
    choices = [{"name": d, "value": display_map[d]} for d in display_choices]
    choices.append({"name": "⬅️  Back", "value": "__BACK__"})
    choices.append({"name": "❌ Abort", "value": "__ABORT__"})
    selected = questionary.select(
        prompt_text,
        choices=choices
    ).ask()
    if selected == "__BACK__":
        return "__BACK__"
    if selected == "__ABORT__":
        print("Aborted by user.")
        sys.exit(0)
    return selected

def prompt_llm_cache_for_space(base_url, auth, all_spaces=False, dry_run=False, batch_size=5):
    if all_spaces:
        spaces = get_all_spaces(base_url, auth)
        spaces = [s for s in spaces if not s['key'].startswith('~')]
        for idx, space in enumerate(spaces, 1):
            space_key = space['key']
            cache_path = f"cache/{space_key}_crawl_cache.json"
            if not os.path.exists(cache_path):
                print(f"[{idx}/{len(spaces)}] Crawl cache not found for space {space_key} at {cache_path}. Skipping.")
                logger.warning(f"Crawl cache not found for space {space_key} at {cache_path}. Skipping.")
                continue
            print(f"[{idx}/{len(spaces)}] Processing LLM cache for space {space_key}...")
            logger.info(f"Processing LLM cache for space {space_key}...")
            t0 = time.time()
            summary = process_space_with_llm_cache_granular(space_key, base_url, auth, cache_path, batch_size=batch_size, dry_run=dry_run)
            print_llm_cache_summary(summary)
            print(f"LLM cache processing complete for space {space_key} in {time.time()-t0:.1f}s.")
            logger.info(f"LLM cache processing complete for space {space_key} in {time.time()-t0:.1f}s.")
        print("All spaces processed.")
        logger.info("All spaces processed.")
        return
    space_key = prompt_space_key(base_url, auth)
    if space_key in (None, "__BACK__"):
        print("Returning to previous menu.")
        logger.info("Returning to previous menu.")
        return
    if space_key == "__ABORT__":
        safe_exit()
    cache_path = f"cache/{space_key}_crawl_cache.json"
    if not os.path.exists(cache_path):
        print(f"Crawl cache not found for space {space_key} at {cache_path}.")
        logger.warning(f"Crawl cache not found for space {space_key} at {cache_path}.")
        return
    print(f"Processing LLM cache for space {space_key}...")
    logger.info(f"Processing LLM cache for space {space_key}...")
    t0 = time.time()
    summary = process_space_with_llm_cache_granular(space_key, base_url, auth, cache_path, batch_size=batch_size, dry_run=dry_run)
    print_llm_cache_summary(summary)
    print(f"LLM cache processing complete for space {space_key} in {time.time()-t0:.1f}s.")
    logger.info(f"LLM cache processing complete for space {space_key} in {time.time()-t0:.1f}s.")

def robust_llm_post(url, payload, context, error_log_path, rate_limit_delay=2):
    tries = 0
    resp = None
    while tries < 5:
        try:
            resp = requests.post(url, json=payload)
            if resp.status_code == 429 or (resp.status_code == 503 and 'overload' in resp.text.lower()):
                print(f"[WARN] LLM server rate limited or overloaded. Sleeping {rate_limit_delay}s...")
                time.sleep(rate_limit_delay)
                tries += 1
                continue
            resp.raise_for_status()
            return resp.json().get("result", "")
        except Exception as e:
            err_msg = f"[{datetime.now()}] LLM POST error ({context}): {e} (status: {getattr(resp, 'status_code', 'N/A')})\nPayload: {json.dumps(payload)[:200]}...\n"
            with open(error_log_path, "a", encoding="utf-8") as logf:
                logf.write(err_msg)
            print(f"[ERROR] {err_msg.strip()}")
            tries += 1
            time.sleep(rate_limit_delay)
    return f"[ERROR: LLM server failed after {tries} attempts]"

def chunk_text(text, max_size=4000):
    """Split text into chunks of max_size, trying to split at paragraph boundaries."""
    chunks = []
    while len(text) > max_size:
        # Try to split at the last double newline before max_size
        split_idx = text.rfind('\n\n', 0, max_size)
        if split_idx == -1:
            split_idx = max_size
        chunks.append(text[:split_idx])
        text = text[split_idx:]
    if text:
        chunks.append(text)
    return [c.strip() for c in chunks if c.strip()]

def extract_json_from_llm_output(text):
    """Extracts and parses the first JSON code block from LLM output. Returns a Python dict if successful, else None."""
    match = re.search(r"```json\s*(\{[\s\S]+?\})\s*```", text)
    if not match:
        match = re.search(r"```\s*(\{[\s\S]+?\})\s*```", text)
    if match:
        json_str = match.group(1)
        try:
            return json.loads(json_str)
        except Exception as e:
            logger.warning(f"Failed to parse JSON from code block: {e}")
            return None
    match = re.search(r"(\{[\s\S]+\})", text)
    if match:
        json_str = match.group(1)
        try:
            return json.loads(json_str)
        except Exception as e:
            logger.warning(f"Failed to parse JSON from fallback: {e}")
            return None
    return None

def process_space_with_llm_cache_granular(space_key, base_url, auth, space_cache_path, llm_server_url="http://localhost:5051", batch_size=5, dry_run=False, search_query=None, rate_limit_delay=2):
    """Wraps process_space_with_llm_cache to add granular CLI/log feedback for each page and step."""
    error_log_path = os.path.join("cache", f"llm_{space_key}_errors.log")
    if not check_llm_server_health(llm_server_url):
        print(f"[ERROR] LLM server at {llm_server_url} is not healthy. Aborting batch.")
        logger.error(f"LLM server at {llm_server_url} is not healthy. Aborting batch.")
        return {"space_key": space_key, "error": "LLM server not healthy"}
    with open(space_cache_path, "r", encoding="utf-8") as f:
        crawl_cache = json.load(f)
    page_ids = crawl_cache.get("processed_ids") or list(crawl_cache.get("page_metadata", {}).keys())
    # LLM cache and error log paths for the space (in subdirectory, with full filename)
    llm_space_dir = os.path.join("cache", "llm", space_key)
    os.makedirs(llm_space_dir, exist_ok=True)
    llm_cache_path = os.path.join(llm_space_dir, f"llm_{space_key}_llm_cache.json")
    error_log_path = os.path.join(llm_space_dir, f"llm_{space_key}_errors.log")
    # Load or initialize the LLM cache array
    if os.path.exists(llm_cache_path):
        with open(llm_cache_path, "r", encoding="utf-8") as f:
            llm_cache_arr = json.load(f)
    else:
        llm_cache_arr = []
    processed, skipped, errors = [], [], []

    def process_single_page(page_id, idx, total):
        doc_ref = {"space_key": space_key, "page_id": page_id}
        # Check if this page is already in the cache array (defensive: only check dicts)
        if any(isinstance(entry, dict) and entry.get("reference", {}).get("page_id") == page_id for entry in llm_cache_arr):
            print(f"[{idx}/{total}] Skipping already cached page {page_id}")
            logger.info(f"[SKIP] [{page_id}] Already cached")
            skipped.append(page_id)
            return None
        if dry_run:
            print(f"[{idx}/{total}] [DRY RUN] Would process page {page_id}")
            logger.info(f"[DRY RUN] [{page_id}] Would process page")
            return None
        print(f"[{idx}/{total}] Processing page {page_id}...")
        logger.info(f"[STAGE] [{page_id}] Start processing page")
        # Pass 1: Summarize
        logger.info(f"[STAGE] [{page_id}] Summarization started")
        # Fetch Confluence page content as Markdown and cache it
        cache_dir = os.path.join("cache", "page_text")
        os.makedirs(cache_dir, exist_ok=True)
        cache_path = os.path.join(cache_dir, f"{space_key}_{page_id}.md")
        try:
            api_url = f"{base_url}/rest/api/content/{page_id}"
            resp = requests.get(api_url, params={'expand': 'body.storage'}, auth=auth, timeout=60)
            resp.raise_for_status()
            storage_html = resp.json().get('body', {}).get('storage', {}).get('value', '')
            markdown = confluence_storage_to_markdown(storage_html)
            # Write atomically
            with tempfile.NamedTemporaryFile(delete=False, mode='w', encoding='utf-8', dir=cache_dir) as tf:
                tf.write(markdown)
                temp_path = tf.name
            shutil.move(temp_path, cache_path)
            logger.info(f"[STAGE] [{page_id}] Page content fetched and cached")
        except Exception as e:
            print(f"    [ERROR] Failed to fetch or cache page content for page {page_id}: {e}")
            logger.error(f"[ERROR] [{page_id}] Failed to fetch or cache page content: {e}")
            summary = f"[ERROR: Failed to fetch or cache page content: {e}]"
            llm_data = {"reference": doc_ref, "summary": summary}
            with open(llm_cache_path, "w", encoding="utf-8") as f:
                json.dump(llm_data, f, indent=2)
            processed.append(page_id)
            return llm_data if isinstance(llm_data, dict) else None
        print(f"    Step 1/3: Summarizing page content...")
        logger.info(f"[STAGE] [{page_id}] Step 1/3: Summarizing page content")
        # Read the cached markdown and pass to LLM (keep in memory for all chunking/LLM steps)
        with open(cache_path, 'r', encoding='utf-8') as f:
            page_text_for_llm = f.read()
        # --- CHUNKING LOGIC FOR SUMMARY ---
        def llm_with_chunking(prompt, context, step_name):
            # Check for empty or whitespace-only context
            if not context or not str(context).strip():
                logger.warning(f"[SKIP] [{page_id}] {step_name} skipped: empty context")
                return "[ERROR: Empty context, skipping LLM call]"
            # Check for non-string context
            if not isinstance(context, str):
                logger.warning(f"[SKIP] [{page_id}] {step_name} skipped: context is not a string (type: {type(context)})")
                return f"[ERROR: Non-string context (type: {type(context)}), skipping LLM call]"
            # For metadata/refined_metadata steps, check for valid JSON if the prompt expects it
            if "JSON object" in prompt and not re.search(r'\{.*\}', context, re.DOTALL):
                logger.warning(f"[SKIP] [{page_id}] {step_name} skipped: context does not appear to contain JSON")
                return "[ERROR: Context does not appear to contain JSON, skipping LLM call]"
            logger.info(f"[STAGE] [{page_id}] {step_name} started (context length: {len(context)})")
            if len(context) <= 4000:
                logger.info(f"[STAGE] [{page_id}] {step_name} single call (no chunking)")
                return robust_llm_post(f"{llm_server_url}/llm/generate", {
                    "prompt": prompt,
                    "context": context,
                    "model": "llama3.3"
                }, context=f"{step_name} {page_id}", error_log_path=error_log_path, rate_limit_delay=rate_limit_delay)
            # Chunking required
            print(f"    [CHUNKING] {step_name}: Context too large ({len(context)} chars), splitting into chunks...")
            logger.info(f"[CHUNK] [{page_id}] {step_name}: Context too large ({len(context)} chars), splitting into chunks...")
            chunks = chunk_text(context, max_size=4000)
            logger.info(f"[CHUNK] [{page_id}] {step_name}: {len(chunks)} chunks created")
            chunk_summaries = []
            for i, chunk in enumerate(chunks):
                print(f"      [CHUNK {i+1}/{len(chunks)}] Sending chunk to LLM ({len(chunk)} chars)...")
                logger.info(f"[CHUNK] [{page_id}] {step_name}: Processing chunk {i+1}/{len(chunks)} (length: {len(chunk)})")
                chunk_summary = robust_llm_post(f"{llm_server_url}/llm/generate", {
                    "prompt": prompt,
                    "context": chunk,
                    "model": "llama3.3"
                }, context=f"{step_name} chunk {i+1}/{len(chunks)} {page_id}", error_log_path=error_log_path, rate_limit_delay=rate_limit_delay)
                chunk_summaries.append(chunk_summary)
                logger.info(f"[CHUNK] [{page_id}] {step_name}: Chunk {i+1}/{len(chunks)} complete")
            # Combine chunk summaries
            print(f"      [CHUNKING] Combining {len(chunks)} chunk results with LLM...")
            logger.info(f"[CHUNK] [{page_id}] {step_name}: Combining {len(chunks)} chunk results with LLM")
            combined = robust_llm_post(f"{llm_server_url}/llm/generate", {
                "prompt": f"Combine the following {step_name.lower()} results into a single, coherent result:",
                "context": '\n\n'.join(chunk_summaries),
                "model": "llama3.3"
            }, context=f"{step_name} combine chunks {page_id}", error_log_path=error_log_path, rate_limit_delay=rate_limit_delay)
            logger.info(f"[CHUNK] [{page_id}] {step_name}: Chunks combined")
            return combined
        # ---
        summary = llm_with_chunking(f"Summarize the following Confluence page:", page_text_for_llm, "Summarize")
        llm_data = {"reference": doc_ref, "summary": summary}
        logger.info(f"[STAGE] [{page_id}] Summarization complete")
        print(f"    Step 1/3 complete: Wrote summary to {llm_cache_path}")
        logger.info(f"[STAGE] [{page_id}] Step 1/3 complete: Wrote summary to {llm_cache_path}")
        if isinstance(summary, str) and summary.startswith('[ERROR'):
            print(f"    [ERROR] Summary step failed for page {page_id}: {summary}")
            logger.error(f"[ERROR] [{page_id}] Summary step failed: {summary}")
        # Pass 2: Extract metadata from summary
        print(f"    Step 2/3: Extracting metadata from summary...{' (chunking may apply)' if len(str(summary)) > 4000 else ''}")
        logger.info(f"[STAGE] [{page_id}] Step 2/3: Extracting metadata from summary")
        metadata_prompt = (
            "Extract structured metadata from the following summary. Respond ONLY with a valid JSON object as a code block (```json ... ```), and do not include any extra text or explanation. If a field is missing, use null or an empty value.\n\nSummary:"
        )
        metadata_from_summary = llm_with_chunking(metadata_prompt, summary, "Metadata Extraction")
        llm_data["metadata_from_summary"] = metadata_from_summary
        meta_json = extract_json_from_llm_output(metadata_from_summary)
        if meta_json is not None:
            llm_data["metadata_from_summary_json"] = meta_json
            logger.info(f"[JSON] [{page_id}] Metadata extraction JSON parsed successfully")
        else:
            logger.warning(f"[JSON] [{page_id}] Metadata extraction JSON parsing failed")
            llm_data["metadata_from_summary_json"] = None
        logger.info(f"[STAGE] [{page_id}] Metadata extraction complete")
        print(f"    Step 2/3 complete: Wrote metadata to {llm_cache_path}")
        logger.info(f"[STAGE] [{page_id}] Step 2/3 complete: Wrote metadata to {llm_cache_path}")
        if isinstance(metadata_from_summary, str) and metadata_from_summary.startswith('[ERROR'):
            print(f"    [ERROR] Metadata extraction failed for page {page_id}: {metadata_from_summary}")
            logger.error(f"[ERROR] [{page_id}] Metadata extraction failed: {metadata_from_summary}")
        # Pass 3: Refine metadata
        print(f"    Step 3/3: Refining metadata for analytics...{' (chunking may apply)' if len(str(metadata_from_summary)) > 4000 else ''}")
        logger.info(f"[STAGE] [{page_id}] Step 3/3: Refining metadata for analytics")
        refine_prompt = (
            "Refine and generalize the following metadata for analytics. Respond ONLY with a valid JSON object as a code block (```json ... ```), and do not include any extra text or explanation. If a field is missing, use null or an empty value.\n\nMetadata:"
        )
        refined_metadata = llm_with_chunking(refine_prompt, metadata_from_summary, "Refine Metadata")
        llm_data["refined_metadata"] = refined_metadata
        refined_json = extract_json_from_llm_output(refined_metadata)
        if refined_json is not None:
            llm_data["refined_metadata_json"] = refined_json
            logger.info(f"[JSON] [{page_id}] Refined metadata JSON parsed successfully")
        else:
            logger.warning(f"[JSON] [{page_id}] Refined metadata JSON parsing failed")
            llm_data["refined_metadata_json"] = None
        logger.info(f"[STAGE] [{page_id}] Metadata refinement complete")
        print(f"    Step 3/3 complete: Wrote refined metadata to {llm_cache_path}")
        logger.info(f"[STAGE] [{page_id}] Step 3/3 complete: Wrote refined metadata to {llm_cache_path}")
        if isinstance(refined_metadata, str) and refined_metadata.startswith('[ERROR'):
            print(f"    [ERROR] Metadata refinement failed for page {page_id}: {refined_metadata}")
            logger.error(f"[ERROR] [{page_id}] Metadata refinement failed: {refined_metadata}")
        # Only now, after all LLM steps for this page, delete the cached page content file
        if cache_path and os.path.exists(cache_path):
            try:
                os.remove(cache_path)
                print(f"    [CLEANUP] Deleted cached page content: {cache_path}")
                logger.info(f"[CLEANUP] [{page_id}] Deleted cached page content: {cache_path}")
            except Exception as e:
                print(f"    [WARN] Could not delete cached page content: {e}")
                logger.warning(f"[CLEANUP] [{page_id}] Could not delete cached page content: {e}")
        # Instead of writing per-page file, update the array and write the whole array
        if isinstance(llm_data, dict):
            llm_cache_arr.append(llm_data)
            with open(llm_cache_path, "w", encoding="utf-8") as f:
                json.dump(llm_cache_arr, f, indent=2)
            logger.info(f"[STAGE] [{page_id}] LLM data appended and cache written")
        else:
            logger.error(f"[ERROR] [{page_id}] Skipping malformed llm_data: {llm_data}")
        processed.append(page_id)
        logger.info(f"[STAGE] [{page_id}] Processing complete")
        return llm_data if isinstance(llm_data, dict) else None

    # Parallel processing using ThreadPoolExecutor
    total_pages = len(page_ids)
    with ThreadPoolExecutor(max_workers=batch_size) as executor:
        futures = {executor.submit(process_single_page, page_id, idx+1, total_pages): page_id for idx, page_id in enumerate(page_ids)}
        for future in as_completed(futures):
            result = future.result()
            if result is not None:
                processed.append(result["reference"]["page_id"])
    summary = {
        "space_key": space_key,
        "total": len(page_ids),
        "processed": processed,
        "skipped": skipped,
        "errors": errors,
        "llm_cache_path": llm_cache_path,
        "llm_error_log": error_log_path
    }
    return summary

def print_llm_cache_summary(summary):
    if not summary:
        print("No summary available.")
        logger.warning("No summary available.")
        return
    if "error" in summary:
        print(f"[ERROR] {summary.get('error')}")
        logger.error(f"[ERROR] {summary.get('error')}")
        return
    print(f"\n=== LLM Cache Summary for {summary['space_key']} ===")
    logger.info(f"=== LLM Cache Summary for {summary['space_key']} ===")
    print(f"  Total pages: {summary['total']}")
    print(f"  Processed: {len(summary['processed'])}")
    print(f"  Skipped (already cached): {len(summary['skipped'])}")
    print(f"  Errors: {len(summary['errors'])}")
    print(f"  LLM cache path: {summary['llm_cache_path']}")
    print(f"  LLM error log: {summary['llm_error_log']}")
    logger.info(f"  Total pages: {summary['total']}")
    logger.info(f"  Processed: {len(summary['processed'])}")
    logger.info(f"  Skipped (already cached): {len(summary['skipped'])}")
    logger.info(f"  Errors: {len(summary['errors'])}")
    logger.info(f"  LLM cache path: {summary['llm_cache_path']}")
    logger.info(f"  LLM error log: {summary['llm_error_log']}")
    if summary['errors']:
        print(f"  Error log: {summary['llm_error_log']}")
        logger.warning(f"  Error log: {summary['llm_error_log']}")
        for pid, err in summary['errors'][:5]:
            print(f"    - {pid}: {err}")
            logger.warning(f"    - {pid}: {err}")
        if len(summary['errors']) > 5:
            print(f"    ...and {len(summary['errors'])-5} more.")
            logger.warning(f"    ...and {len(summary['errors'])-5} more.")

def prompt_llm_cache_all_spaces(base_url, auth, dry_run=False, batch_size=5):
    prompt_llm_cache_for_space(base_url, auth, all_spaces=True, dry_run=dry_run, batch_size=batch_size)

def prompt_llm_search_analytics(base_url, auth):
    """Prompt user to select a space and search/analyze LLM metadata."""
    space_key = prompt_space_key(base_url, auth)
    if not space_key:
        print("No space selected.")
        return
    llm_cache_path = os.path.join("cache", f"llm_{space_key}_llm_cache.json")
    if not os.path.exists(llm_cache_path):
        print(f"No LLM cache found for space {space_key}.")
        return
    query = input("Enter search term (keyword, topic, client, etc.): ").strip().lower()
    if not query:
        print("No search term entered.")
        return
    # Gather all LLM cache files for the space
    files = [os.path.join(llm_cache_path, f) for f in os.listdir(llm_cache_path) if f.endswith('.json')]
    matches = []
    for fpath in files:
        with open(fpath, "r", encoding="utf-8") as f:
            doc = json.load(f)
        meta = doc.get("metadata_from_summary", {})
        fields = [
            doc.get("summary", ""),
            json.dumps(meta),
            " ".join(str(v) for v in meta.values() if isinstance(v, (str, list)))
        ]
        # Fuzzy match: check if query is in any field (case-insensitive)
        if any(query in str(field).lower() for field in fields):
            matches.append({
                "Page ID": doc["reference"]["page_id"],
                "Title": meta.get("title", "[No Title]"),
                "Type": meta.get("document_type", ""),
                "Categories": ", ".join(meta.get("categories", [])),
                "Topics": ", ".join(meta.get("topics", [])),
                "Summary": doc.get("summary", "")[:120] + ("..." if len(doc.get("summary", "")) > 120 else "")
            })
    if not matches:
        print("No matches found.")
        return
    print(f"\nFound {len(matches)} matching documents in space {space_key}:")
    print(tabulate(matches, headers="keys", tablefmt="github"))

def prompt_generate_redundancy_report(base_url, auth):
    space_key = prompt_space_key(base_url, auth)
    if not space_key:
        print("No space selected.")
        return
    print(f"Generating redundancy & similarity report for space {space_key}...")
    report_path = generate_redundancy_similarity_report(space_key)
    if report_path:
        print(f"Redundancy report written to: {report_path}")
    else:
        print("Failed to generate redundancy report.")

def prompt_generate_coverage_heatmap(base_url, auth):
    space_key = prompt_space_key(base_url, auth)
    if not space_key:
        print("No space selected.")
        return
    print(f"Generating coverage heatmap for space {space_key}...")
    report_path = generate_coverage_heatmap(space_key)
    if report_path:
        print(f"Coverage heatmap written to: {report_path}")
    else:
        print("Failed to generate coverage heatmap.")

def prompt_run_llm_cache_process(base_url, auth):
    """Prompt user to select a space, set batch size and dry run, then run process_space_with_llm_cache directly."""
    space_key = prompt_space_key(base_url, auth)
    if space_key in (None, "__BACK__"):
        print("Returning to previous menu.")
        return
    if space_key == "__ABORT__":
        print("Aborted by user.")
        sys.exit(0)
    # Prompt for batch size
    batch_size = questionary.text("Enter batch size (default 5):", default="5").ask()
    try:
        batch_size = int(batch_size)
    except Exception:
        batch_size = 5
    # Prompt for dry run
    dry_run = questionary.confirm("Run in dry run mode? (no files will be written)", default=False).ask()
    cache_path = f"cache/{space_key}_crawl_cache.json"
    if not os.path.exists(cache_path):
        print(f"Crawl cache not found for space {space_key} at {cache_path}.")
        return
    print(f"Running LLM cache process for space {space_key} (batch_size={batch_size}, dry_run={dry_run})...")
    summary = process_space_with_llm_cache(space_key, base_url, auth, cache_path, batch_size=batch_size, dry_run=dry_run)
    print_llm_cache_summary(summary)
    print(f"LLM cache process complete for space {space_key}.")

def safe_exit(msg="Exiting. Goodbye!"):
    print(msg)
    logger.info(msg)
    sys.exit(0)

def prompt_start_api_server():
    print("Starting API server...")
    logger.info("Starting API server...")
    result = subprocess.run([sys.executable, "server_manager.py", "start"], capture_output=True, text=True)
    logger.info(result.stdout or result.stderr)
    print(result.stdout or result.stderr)

def prompt_stop_api_server():
    print("Stopping API server...")
    logger.info("Stopping API server...")
    result = subprocess.run([sys.executable, "server_manager.py", "stop"], capture_output=True, text=True)
    logger.info(result.stdout or result.stderr)
    print(result.stdout or result.stderr)

def prompt_start_llm_server():
    print("Starting LLM server...")
    logger.info("Starting LLM server...")
    result = subprocess.run([sys.executable, "server_manager.py", "start-llm"], capture_output=True, text=True)
    logger.info(result.stdout or result.stderr)
    print(result.stdout or result.stderr)

def prompt_stop_llm_server():
    print("Stopping LLM server...")
    logger.info("Stopping LLM server...")
    result = subprocess.run([sys.executable, "server_manager.py", "stop-llm"], capture_output=True, text=True)
    logger.info(result.stdout or result.stderr)
    print(result.stdout or result.stderr)

def prompt_view_api_server_logs():
    print("--- API Server Logs (last 40 lines) ---")
    import subprocess
    try:
        result = subprocess.run(["tail", "-n", "40", "server.log"], capture_output=True, text=True)
        print(result.stdout or result.stderr)
    except Exception as e:
        print(f"[ERROR] Could not read server.log: {e}")
        logger.error(f"Could not read server.log: {e}")

def prompt_view_llm_server_logs():
    print("--- LLM Server Logs (last 40 lines) ---")
    import subprocess
    try:
        result = subprocess.run(["tail", "-n", "40", "llm_server.log"], capture_output=True, text=True)
        print(result.stdout or result.stderr)
    except Exception as e:
        print(f"[ERROR] Could not read llm_server.log: {e}")
        logger.error(f"Could not read llm_server.log: {e}")

def prompt_analyze_server_logs():
    print("--- Analyzing API and LLM Server Logs ---")
    import re
    def analyze_log(log_path):
        if not os.path.exists(log_path):
            return f"[ERROR] Log file not found: {log_path}", None
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        errors = [l for l in lines if re.search(r'\bERROR\b', l, re.IGNORECASE)]
        warns = [l for l in lines if re.search(r'\bWARN(ING)?\b', l, re.IGNORECASE)]
        restarts = [l for l in lines if re.search(r'start(ed|ing)|restart', l, re.IGNORECASE)]
        return None, {
            "total": len(lines),
            "errors": len(errors),
            "warnings": len(warns),
            "restarts": len(restarts),
            "last_5_errors": errors[-5:],
            "last_5_warnings": warns[-5:],
            "last_3_restarts": restarts[-3:]
        }
    for log_name, log_path in [("API Server", "server.log"), ("LLM Server", "llm_server.log")]:
        print(f"\n=== {log_name} Log Analysis ===")
        err, stats = analyze_log(log_path)
        if err:
            print(err)
            logger.error(err)
            continue
        print(f"  Total lines: {stats['total']}")
        print(f"  Errors: {stats['errors']}")
        print(f"  Warnings: {stats['warnings']}")
        print(f"  Restarts: {stats['restarts']}")
        if stats['last_5_errors']:
            print("  Last 5 errors:")
            for l in stats['last_5_errors']:
                print("    ", l.strip())
        if stats['last_5_warnings']:
            print("  Last 5 warnings:")
            for l in stats['last_5_warnings']:
                print("    ", l.strip())
        if stats['last_3_restarts']:
            print("  Last 3 restarts:")
            for l in stats['last_3_restarts']:
                print("    ", l.strip())
        logger.info(f"Analyzed {log_name} log: {stats}")

def test_api_server():
    """Test the health of the API server and print CLI output."""
    import requests
    logger.info("Testing API server health...")
    try:
        resp = requests.get("http://localhost:5050/health", timeout=5)
        if resp.status_code == 200 and resp.json().get("status") == "ok":
            print(f"{Fore.GREEN}API server is healthy!{Style.RESET_ALL}")
            logger.info("API server is healthy!")
        else:
            print(f"{Fore.RED}API server unhealthy: {resp.status_code} {resp.text}{Style.RESET_ALL}")
            logger.error(f"API server unhealthy: {resp.status_code} {resp.text}")
    except Exception as e:
        print(f"{Fore.RED}API server health check failed: {e}{Style.RESET_ALL}")
        logger.error(f"API server health check failed: {e}")

def test_llm_server():
    """Test the health of the LLM server and print CLI output."""
    import requests
    logger.info("Testing LLM server health...")
    try:
        resp = requests.get("http://localhost:5051/health", timeout=5)
        if resp.status_code == 200 and resp.json().get("status") == "ok":
            print(f"{Fore.GREEN}LLM server is healthy!{Style.RESET_ALL}")
            logger.info("LLM server is healthy!")
        else:
            print(f"{Fore.RED}LLM server unhealthy: {resp.status_code} {resp.text}{Style.RESET_ALL}")
            logger.error(f"LLM server unhealthy: {resp.status_code} {resp.text}")
    except Exception as e:
        print(f"{Fore.RED}LLM server health check failed: {e}{Style.RESET_ALL}")
        logger.error(f"LLM server health check failed: {e}")

def run_cli_main_menu(base_url, auth):
    try:
        while True:
            choice = main_menu()
            if choice in (None, "__BACK__"):
                print("Returning to previous menu.")
                continue
            if choice == "__ABORT__":
                safe_exit()
            if choice == "start_api_server":
                prompt_start_api_server()
            elif choice == "stop_api_server":
                prompt_stop_api_server()
            elif choice == "start_llm_server":
                prompt_start_llm_server()
            elif choice == "stop_llm_server":
                prompt_stop_llm_server()
            elif choice == "view_api_server_logs":
                prompt_view_api_server_logs()
            elif choice == "view_llm_server_logs":
                prompt_view_llm_server_logs()
            elif choice == "analyze_server_logs":
                prompt_analyze_server_logs()
            elif choice == "llm_cache_space":
                prompt_llm_cache_for_space(base_url, auth)
            elif choice == "llm_cache_all":
                prompt_llm_cache_all_spaces(base_url, auth)
            elif choice == "llm_cache_advanced":
                prompt_run_llm_cache_process(base_url, auth)
            elif choice == "redundancy_report":
                prompt_generate_redundancy_report(base_url, auth)
            elif choice == "coverage_heatmap":
                prompt_generate_coverage_heatmap(base_url, auth)
            elif choice == "llm_search_analytics":
                prompt_llm_search_analytics(base_url, auth)
            elif choice == "test_api_server":
                test_api_server()
            elif choice == "test_llm_server":
                test_llm_server()
            elif choice == "Exit":
                safe_exit()
            else:
                print(f"[WARN] Unrecognized menu option: {choice}")
    except KeyboardInterrupt:
        safe_exit("Interrupted by user. Exiting.")

# Optional: Utility to clean up old files in cache/page_text (not invoked automatically)
def cleanup_old_page_text_cache(max_age_hours=24):
    import time
    cache_dir = os.path.join("cache", "page_text")
    if not os.path.isdir(cache_dir):
        return
    now = time.time()
    for fname in os.listdir(cache_dir):
        fpath = os.path.join(cache_dir, fname)
        if os.path.isfile(fpath):
            age_hours = (now - os.path.getmtime(fpath)) / 3600
            if age_hours > max_age_hours:
                try:
                    os.remove(fpath)
                    print(f"[CLEANUP] Deleted old cached file: {fpath}")
                except Exception as e:
                    print(f"[WARN] Could not delete old cached file: {fpath} ({e})")

# The prompt_with_validation and BATCH_PROMPT should be imported from cli.py or constants.py 