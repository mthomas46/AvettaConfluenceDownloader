"""
Confluence Downloader Script
- Downloads Confluence pages as text files and generates a metrics report.
- Supports command-line arguments and interactive prompts.
- Features colorized output, dry run mode, and error handling.
"""

# === Imports ===
import argparse
import os
import re
import requests
import getpass
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
from tqdm import tqdm
import sys
from itertools import cycle
from cli_helpers import print_section, main_menu, select_mode, spinner, prompt_with_validation, prompt_space_key, run_cli_main_menu
import json
import time
import threading
import math
from yaspin import yaspin
import asyncio
import httpx

if not (sys.version_info.major == 3 and sys.version_info.minor in (11, 12)):
    print("""
WARNING: This script is tested and supported only on Python 3.11 and 3.12.
Some dependencies (e.g., lxml) may not work on Python 3.13+ or older versions.
Please use Python 3.12 or 3.11 for best compatibility.
""")
    sys.exit(1)

# Load .env file if present
load_dotenv()

# === Colorama Setup ===
try:
    from colorama import init as colorama_init, Fore, Style
    colorama_init()
except ImportError:
    class Dummy:
        def __getattr__(self, name): return ''
    Fore = Style = Dummy()

# === Argument Parsing ===
__version__ = "1.0.0"

def get_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Confluence Downloader")
    parser.add_argument('--base-url', help='Confluence base URL')
    parser.add_argument('--username', help='Confluence username/email')
    parser.add_argument('--mode', choices=['1', '2', '3', '4'], help='1: entire space, 2: by parent page, 3: search by title, 4: generate space structure report only')
    parser.add_argument('--output-dir', help='Output directory')
    parser.add_argument('--metrics-only', action='store_true', help='Generate metrics report only')
    parser.add_argument('--parent-url', help='Parent page URL (for mode 2)')
    parser.add_argument('--space-key', help='Space key (for mode 1)')
    parser.add_argument('--dry-run', action='store_true', help='Dry run mode')
    parser.add_argument('--version', action='version', version=f'%(prog)s {__version__}', help='Show version and exit')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose (DEBUG) logging')
    # New CLI options for crawling
    parser.add_argument('--batch-size', type=int, default=20, help='Batch size for crawling (default: 20)')
    parser.add_argument('--threads', type=int, default=8, help='Number of threads for crawling (default: 8)')
    parser.add_argument('--label-filter', type=str, nargs='*', help='Only include pages with these labels (space separated)')
    parser.add_argument('--title-filter', type=str, help='Only include pages with this substring in the title')
    parser.add_argument('--page-type-filter', type=str, help='Only include pages of this type (e.g., page, blogpost)')
    parser.add_argument('--output-format', type=str, choices=['md', 'json', 'both'], default='md', help='Output format for space structure report (md, json, or both). Default: md')
    return parser.parse_args()

# === Interactive Credential Prompt ===
def prompt_credentials():
    """Prompt user for credentials if not provided via CLI."""
    default_url = "https://avetta.atlassian.net/wiki"
    base_url = input(f"Confluence base URL [default: {default_url}]: ").strip().rstrip('/') or default_url
    if not base_url.startswith("http://") and not base_url.startswith("https://"):
        base_url = "https://" + base_url
    username = input("Confluence username/email: ").strip()
    api_token = getpass.getpass("Confluence API token: ").strip()
    return base_url, username, api_token

import logging

# Setup logging
logging.basicConfig(filename='confluence_downloader.log', level=logging.INFO, 
                    format='%(asctime)s %(levelname)s: %(message)s')

def sanitize_filename(name):
    """Sanitize string for safe filename usage."""
    return re.sub(r'[\\/*?\":<>|]', '_', name)

def consolidate_markdown_files(root_dir, output_filename="Consolidated.md"):
    """Recursively collect and combine all .md files under root_dir into a single enhanced markdown file."""
    import glob
    import logging
    consolidated = []
    seen_lines = set()
    # Recursively find all .md files (excluding metrics and consolidated)
    for path in glob.glob(os.path.join(root_dir, "**", "*.md"), recursive=True):
        fname = os.path.basename(path).lower()
        if fname in {"metrics.md", output_filename.lower()}: continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            # Add section header for each file
            consolidated.append(f"\n---\n\n# {os.path.splitext(os.path.basename(path))[0].replace('_',' ').replace('-',' ')}\n\n")
            for line in lines:
                if line.strip() and line not in seen_lines:
                    consolidated.append(line)
                    seen_lines.add(line)
        except Exception as e:
            logging.error(f"Error reading {path}: {e}")
    # Enhance readability: join and write
    out_path = os.path.join(root_dir, output_filename)
    try:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("""# Consolidated Developer Documentation\n\nThis document combines all unique information from Markdown files in this directory.\n\n""")
            f.writelines(consolidated)
        print(f"{Fore.GREEN}Consolidated file written to {out_path}{Style.RESET_ALL}")
        logging.info(f"Consolidated Markdown written to {out_path}")
    except Exception as e:
        print(f"{Fore.RED}Error writing consolidated file: {e}{Style.RESET_ALL}")
        logging.error(f"Error writing consolidated file: {e}")

def unique_filename(filename, output_dir, dir_path):
    """Generate a unique filename if a file already exists on disk in the target directory."""
    full_path = os.path.join(dir_path, filename)
    if not os.path.exists(full_path):
        return filename
    name, ext = os.path.splitext(filename)
    i = 2
    new_filename = f"{name}_{i}{ext}"
    while os.path.exists(os.path.join(dir_path, new_filename)):
        i += 1
        new_filename = f"{name}_{i}{ext}"
    return new_filename

def search_pages_by_title(base_url, auth, search_term):
    """Search for Confluence pages by title."""
    results = []
    start, limit = 0, 25
    while True:
        params = {
            'cql': f'title~"{search_term}" and type=page',
            'limit': limit,
            'start': start,
            'expand': 'body.storage,ancestors,title,version,space,history'
        }
        try:
            r = requests.get(f"{base_url}/rest/api/content/search", params=params, auth=auth)
            r.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"{Fore.RED}Error searching pages: {e}{Style.RESET_ALL}")
            break
        data = r.json()
        results.extend(data.get('results', []))
        if data.get('_links', {}).get('next'):
            start += limit
        else:
            break
    return results

def get_space_key_from_url(url):
    """Extract space key from a Confluence URL."""
    match = re.search(r'/spaces/([^/]+)', url)
    return match.group(1) if match else None

def get_page_id_from_url(url, base_url=None, auth=None):
    """Extract page ID from a Confluence URL."""
    match = re.search(r'pageId=(\d+)', url)
    if match:
        return match.group(1)
    match = re.search(r'/pages/(\d+)', url)
    if match:
        return match.group(1)
    match = re.search(r'/x/([\w]+)', url)
    if match:
        print(f"\n{Fore.YELLOW}[INFO]{Style.RESET_ALL} You have provided a Confluence short link (e.g. /x/ABC123).\n"
              "Confluence Cloud does not support API resolution of short links.\n"
              "To proceed, open the short link in your browser and copy the full URL after redirection.\n")
    return None

# === API Functions ===
def get_all_pages_in_space(base_url, auth, space_key):
    """Fetch all pages in a Confluence space."""
    pages, start, limit = [], 0, 50
    while True:
        params = {
            'spaceKey': space_key, 'type': 'page', 'limit': limit, 'start': start,
            'expand': 'body.storage,ancestors,title,version,space,history'
        }
        try:
            r = requests.get(f"{base_url}/rest/api/content", params=params, auth=auth)
            r.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"{Fore.RED}Error fetching pages: {e}{Style.RESET_ALL}")
            break
        data = r.json()
        pages.extend(data.get('results', []))
        if data.get('_links', {}).get('next'):
            start += limit
        else:
            break
    return pages

def get_descendants(base_url, auth, page_id):
    """Fetch all descendant pages under a parent page."""
    pages, start, limit = [], 0, 50
    while True:
        try:
            r = requests.get(f"{base_url}/rest/api/content/{page_id}/descendant/page", params={
                'limit': limit, 'start': start,
                'expand': 'body.storage,ancestors,title,version,space,history'
            }, auth=auth)
            r.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"{Fore.RED}Error fetching descendants: {e}{Style.RESET_ALL}")
            break
        data = r.json()
        pages.extend(data.get('results', []))
        if data.get('_links', {}).get('next'):
            start += limit
        else:
            break
    # Also add the parent page itself
    try:
        r = requests.get(f"{base_url}/rest/api/content/{page_id}", params={'expand': 'body.storage,ancestors,title,version,space'}, auth=auth)
        r.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"{Fore.RED}Error fetching parent page: {e}{Style.RESET_ALL}")
    else:
        pages.insert(0, r.json())
    return pages

# === File Operations ===
def confluence_storage_to_markdown(storage_html):
    """Convert Confluence storage format (XHTML) to Markdown."""
    soup = BeautifulSoup(storage_html, "lxml")
    lines = []
    def handle_node(node):
        if node.name is None:
            return node.string or ''
        if node.name in ['h1','h2','h3','h4','h5','h6']:
            level = int(node.name[1])
            return f"{'#'*level} {node.get_text(strip=True)}\n\n"
        if node.name == 'p':
            return node.get_text(strip=True) + '\n\n'
        if node.name in ['ul','ol']:
            items = []
            for li in node.find_all('li', recursive=False):
                prefix = '-' if node.name == 'ul' else '1.'
                items.append(f"{prefix} {li.get_text(strip=True)}")
            return '\n'.join(items) + '\n\n'
        if node.name == 'ac:task-list':
            items = []
            for task in node.find_all('ac:task', recursive=False):
                checked = '[x]' if task.find('ac:task-status') and 'complete' in task.find('ac:task-status').text else '[ ]'
                body = task.find('ac:task-body')
                items.append(f"- {checked} {body.get_text(strip=True) if body else ''}")
            return '\n'.join(items) + '\n\n'
        if node.name == 'ac:link':
            page = node.find('ri:page')
            link_body = node.get_text(strip=True)
            if page and page.has_attr('ri:content-title'):
                title = page['ri:content-title']
                return f"[{link_body}]({title})"
            return link_body
        # fallback: recurse
        return ''.join([handle_node(child) for child in node.children])
    for elem in soup.body or soup.children:
        lines.append(handle_node(elem))
    return ''.join(lines).strip()

def save_page(page, output_dir, overwrite_mode="overwrite"):
    """Save a single page as a Markdown file, preserving Confluence hierarchy in the directory structure."""
    title = page.get('title', 'Untitled')
    ancestors = page.get('ancestors', [])
    path_parts = [sanitize_filename(a.get('title', '')) for a in ancestors if a.get('title')]
    dir_path = os.path.join(output_dir, *path_parts) if path_parts else output_dir
    filename = sanitize_filename(title) + ".md"
    filepath = os.path.join(dir_path, filename)

    # Overwrite logic
    if os.path.exists(filepath):
        if isinstance(overwrite_mode, dict) and overwrite_mode.get('mode') == 'ask':
            prompt = (f"File '{filepath}' exists. Overwrite? (y/n/a=all/s=skip all/i=increment all) [default: y]: ")
            resp = input(prompt).strip().lower() or 'y'
            if resp == 'a':
                overwrite_mode['mode'] = 'all'
                logging.info("User selected 'overwrite all' for file conflicts.")
            elif resp == 's':
                overwrite_mode['mode'] = 'skip'
                logging.info("User selected 'skip all' for file conflicts.")
            elif resp == 'i':
                overwrite_mode['mode'] = 'increment'
                logging.info("User selected 'increment all' for file conflicts.")
            elif resp != 'y':
                # User chose not to overwrite, so generate a unique filename
                filename = unique_filename(filename, output_dir, dir_path)
                filepath = os.path.join(dir_path, filename)
                print(f"{Fore.YELLOW}Skipped: {filepath}{Style.RESET_ALL}")
                logging.info(f"User skipped overwriting file: {filepath}")
                return True
        if (isinstance(overwrite_mode, dict) and overwrite_mode.get('mode') == 'skip'):
            filename = unique_filename(filename, output_dir, dir_path)
            filepath = os.path.join(dir_path, filename)
            print(f"{Fore.YELLOW}Skipped: {filepath}{Style.RESET_ALL}")
            logging.info(f"User skipped overwriting file: {filepath}")
            return True
        if (isinstance(overwrite_mode, dict) and overwrite_mode.get('mode') == 'increment'):
            filename = unique_filename(filename, output_dir, dir_path)
            filepath = os.path.join(dir_path, filename)
            # Proceed to save with incremented filename
        # If mode is 'all', always overwrite (do nothing, just overwrite filepath)
        # If overwrite_mode is not a dict (e.g. 'overwrite'), always overwrite

    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        logging.info(f"Attempting to save page '{title}' to '{filepath}'")
        storage_val = page.get('body', {}).get('storage', {}).get('value', '')
        logging.info(f"Converting page '{title}' storage value to markdown.")
        markdown = confluence_storage_to_markdown(storage_val)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(markdown)
        print(f"{Fore.GREEN}Saved:{Style.RESET_ALL} {filepath}")
        logging.info(f"Saved page '{title}' to '{filepath}'")
        return True
    except Exception as e:
        print(f"{Fore.RED}Error saving page '{title}': {e}{Style.RESET_ALL}")
        logging.error(f"Failed to save page '{title}': {e}")
        return False

def get_env_or_prompt(var, prompt, default=None, is_secret=False, stub_values=None):
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

def mask_token(token):
    if not token or len(token) < 8:
        return '***'
    return token[:2] + '*' * (len(token) - 6) + token[-4:]

async def get_page_metadata_with_retry_async(base_url, auth, page_id, timeout=10, max_retries=3, client=None):
    """Async fetch page metadata with timeout and retry logic using httpx."""
    url = f"{base_url}/rest/api/content/{page_id}"
    params = {'expand': 'ancestors,title,version,metadata.labels'}
    for attempt in range(1, max_retries + 1):
        try:
            resp = await client.get(url, params=params, auth=auth, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            if attempt == max_retries:
                return None
            await asyncio.sleep(1.5 * attempt)  # Exponential backoff

def preflight_api_check(base_url, auth):
    """Check API token/session health before crawling."""
    try:
        resp = requests.get(f"{base_url}/rest/api/space", auth=auth, timeout=10)
        resp.raise_for_status()
        return True
    except Exception as e:
        print_section(f"API health check failed: {e}")
        return False

async def crawl_and_report_space_async(
    base_url, auth, space_key, output_dir, batch_size=20, max_workers=8, label_filter=None, title_filter=None, page_type_filter=None, output_format='md'
):
    import os
    from tqdm.asyncio import tqdm as tqdm_async
    from cli_helpers import print_section, spinner
    import json
    import time
    from colorama import Fore, Style
    import math
    from yaspin import yaspin
    # Create output subdirectories
    reports_dir = "reports"
    cache_dir = "cache"
    os.makedirs(reports_dir, exist_ok=True)
    os.makedirs(cache_dir, exist_ok=True)
    cache_path = os.path.join(cache_dir, f"{space_key}_crawl_cache.json")
    report_path = os.path.join(reports_dir, f"space_{space_key}_structure.md")
    json_path = os.path.join(reports_dir, f"space_{space_key}_structure.json")
    error_log_path = os.path.join(cache_dir, f"space_{space_key}_crawl_errors.log")
    toc = []
    # Pre-flight API check (sync for now)
    if not preflight_api_check(base_url, auth):
        print_section("Aborting crawl due to failed API health check.")
        return
    # Load cache
    if os.path.exists(cache_path):
        with open(cache_path, "r", encoding="utf-8") as f:
            cache = json.load(f)
        processed_ids = set(cache.get("processed_ids", []))
        print_section(f"Resuming crawl: {len(processed_ids)} pages already processed.")
    else:
        processed_ids = set()
        cache = {"processed_ids": []}
    # Error log
    error_log = []
    if os.path.exists(error_log_path):
        with open(error_log_path, "r", encoding="utf-8") as f:
            error_log = [line.strip() for line in f.readlines()]
    # Fetch all pages (sync for now)
    with spinner("Fetching all pages in space (GET only)...") as spin:
        pages = get_all_pages_in_space(base_url, auth, space_key)
    if not pages:
        print_section(f"No pages found in space {space_key}.")
        return
    # Apply filters to initial list if needed (for efficiency)
    def page_matches(page):
        if label_filter:
            labels = [l['name'].lower() for l in page.get('metadata', {}).get('labels', {}).get('results', [])]
            if not any(lf in labels for lf in label_filter):
                return False
        if title_filter:
            if title_filter.lower() not in page.get('title', '').lower():
                return False
        if page_type_filter:
            if page.get('type', '').lower() != page_type_filter.lower():
                return False
        return True
    filtered_pages = [p for p in pages if page_matches(p)]
    print_section(f"Filter summary: {len(filtered_pages)} pages matched filters out of {len(pages)} total.")
    if not filtered_pages:
        print_section("No pages matched the provided filters. Exiting.")
        return
    # Build parent/child tree from filtered pages
    children = {}
    roots = []
    filtered_ids = set(p['id'] for p in filtered_pages)
    for page in filtered_pages:
        ancestors = [a for a in page.get('ancestors', []) if a.get('id') in filtered_ids]
        if ancestors:
            parent_id = ancestors[-1]['id']
            children.setdefault(parent_id, []).append(page)
        else:
            roots.append(page)
    # Print and log directories (root and each child path)
    def print_and_log_dir(page, level=0, path=None):
        if path is None:
            path = []
        title = page.get('title', 'Untitled')
        new_path = path + [title]
        dir_path = '/'.join(new_path)
        print(f"{Fore.CYAN}Crawling directory: {dir_path}{Style.RESET_ALL}")
        logging.info(f"Crawling directory: {dir_path}")
        for child in children.get(page['id'], []):
            print_and_log_dir(child, level+1, new_path)
    for root in roots:
        print_and_log_dir(root)
    # Flatten all pages in a list for batch processing
    all_page_ids = [page['id'] for page in filtered_pages]
    to_process = [pid for pid in all_page_ids if pid not in processed_ids]
    processed_count = len(processed_ids)
    page_metadata = {}  # id -> metadata dict
    # Helper to build JSON tree (only for processed pages)
    def build_json_tree(page):
        if page['id'] not in processed_ids:
            return None
        meta = page_metadata.get(page['id'], {})
        node = {
            'id': page['id'],
            'title': page.get('title', 'Untitled'),
            'url': f"{base_url}/pages/{page['id']}",
            'updated': meta.get('updated', 'N/A'),
            'last_viewed': meta.get('last_viewed', 'N/A'),
            'created': meta.get('created', 'N/A'),
            'author': meta.get('author', 'N/A'),
            'labels': meta.get('labels', 'None'),
            'type': meta.get('type', 'page'),
            'parent_id': page['ancestors'][-1]['id'] if page.get('ancestors') else None,
            'ancestor_ids': [a['id'] for a in page.get('ancestors', [])],
            'version': meta.get('version', 'N/A'),
            'num_comments': meta.get('num_comments', 0),
            'num_attachments': meta.get('num_attachments', 0),
            'children': []
        }
        for child in children.get(page['id'], []):
            child_node = build_json_tree(child)
            if child_node:
                node['children'].append(child_node)
        return node
    # Helper to print a mini tree preview in CLI
    def print_tree_preview(page, level=0, max_depth=2, max_lines=10, lines=None):
        if lines is None:
            lines = []
        if len(lines) >= max_lines or level > max_depth:
            return lines
        indent = '  ' * level
        meta = page_metadata.get(page['id'], {})
        title = page.get('title', 'Untitled')
        preview = f"{indent}{Fore.GREEN if page['id'] in processed_ids else Fore.YELLOW}- {title}{Style.RESET_ALL}"
        if meta:
            preview += f" {Fore.CYAN}[{meta.get('author', 'N/A')}, {meta.get('updated', 'N/A')}, {meta.get('labels', 'None')}] {Style.RESET_ALL}"
        lines.append(preview)
        for child in children.get(page['id'], []):
            print_tree_preview(child, level+1, max_depth, max_lines, lines)
        return lines
    # Helper to write the tree structure as Markdown
    def write_tree_md(f, page, level=0):
        indent = "  " * level
        title = page.get('title', 'Untitled')
        url = page.get('_links', {}).get('webui', '')
        # If webui link is present, make it a Markdown link
        if url:
            # If base_url ends with /wiki, remove /wiki for webui links
            base = base_url[:-5] if base_url.endswith('/wiki') else base_url
            full_url = base + url
            f.write(f"{indent}- [{title}]({full_url})\n")
        else:
            f.write(f"{indent}- {title}\n")
        for child in children.get(page['id'], []):
            write_tree_md(f, child, level+1)
    # Main batch loop
    start_time = time.time()
    batch_times = []
    try:
        async with httpx.AsyncClient(http2=True) as client:
            total_pages = len(all_page_ids)
            pbar = tqdm_async(total=total_pages, initial=processed_count, desc="Crawling pages (async)")
            while to_process:
                batch = to_process[:batch_size]
                batch_start = time.time()
                successes, failures = 0, 0
                live_preview_lines = []
                file_results = []
                tasks = []
                for pid in batch:
                    tasks.append(get_page_metadata_with_retry_async(base_url, auth, pid, client=client))
                results = await asyncio.gather(*tasks)
                for idx, result in enumerate(results):
                    pid = batch[idx]
                    page_title = next((p['title'] for p in filtered_pages if p['id'] == pid), pid)
                    with yaspin(text=f"Processing: {page_title}", color="yellow") as file_spin:
                        if result is not None:
                            meta = {
                                'updated': result.get('version', {}).get('when', 'N/A')[:10],
                                'last_viewed': result.get('history', {}).get('lastViewed', {}).get('when', 'N/A')[:10] if result.get('history', {}).get('lastViewed') else 'N/A',
                                'created': result.get('history', {}).get('createdDate', 'N/A')[:10] if result.get('history', {}).get('createdDate') else 'N/A',
                                'author': result.get('version', {}).get('by', {}).get('displayName', 'N/A'),
                                'labels': ', '.join([l['name'] for l in result.get('metadata', {}).get('labels', {}).get('results', [])]) or 'None',
                                'type': result.get('type', 'page'),
                                'version': result.get('version', {}).get('number', 'N/A'),
                                'num_comments': result.get('metadata', {}).get('properties', {}).get('comments', {}).get('count', 0),
                                'num_attachments': result.get('metadata', {}).get('properties', {}).get('attachments', {}).get('count', 0),
                            }
                            # Apply filters (should be redundant, but double check)
                            if label_filter and not any(lf in meta['labels'].lower() for lf in label_filter):
                                file_spin.write(f"{Fore.YELLOW}Skipped (label filter): {page_title}{Style.RESET_ALL}")
                                file_spin.ok("⏭️ ")
                                continue
                            if title_filter and title_filter.lower() not in result.get('title', '').lower():
                                file_spin.write(f"{Fore.YELLOW}Skipped (title filter): {page_title}{Style.RESET_ALL}")
                                file_spin.ok("⏭️ ")
                                continue
                            if page_type_filter and meta['type'].lower() != page_type_filter.lower():
                                file_spin.write(f"{Fore.YELLOW}Skipped (type filter): {page_title}{Style.RESET_ALL}")
                                file_spin.ok("⏭️ ")
                                continue
                            page_metadata[pid] = meta
                            processed_ids.add(pid)
                            successes += 1
                            pbar.update(1)
                            processed_count += 1
                            # Live preview line
                            live_preview_lines.append(f"{Fore.GREEN}{result.get('title', 'Untitled')}{Style.RESET_ALL} | 🕒 {meta['updated']} | 👤 {meta['author']} | 🏷️ {meta['labels']}")
                        else:
                            failures += 1
                            error_log.append(f"{pid}: Failed to fetch after retries.")
                            with open(error_log_path, "a", encoding="utf-8") as ef:
                                ef.write(f"{pid}: Failed to fetch after retries.\n")
                            file_spin.fail("❌ ")
                            file_spin.write(f"{Fore.RED}Failed: {page_title}{Style.RESET_ALL}")
                # Routinely write progress to cache after each batch
                cache["processed_ids"] = list(processed_ids)
                cache["page_metadata"] = page_metadata
                try:
                    with open(cache_path, "w", encoding="utf-8") as f:
                        json.dump(cache, f)
                except Exception as e:
                    print_section(f"Error writing crawl cache: {e}")
                    logging.error(f"Error writing crawl cache: {e}")
                # Update report (Markdown)
                if output_format in ('md', 'both'):
                    with open(report_path, "w", encoding="utf-8") as f:
                        f.write(f"# 📚 Confluence Space Structure: {space_key}\n\n")
                        summary = (
                            f"**Total pages:** {len(pages)}  "
                            f"**Filtered pages:** {len(filtered_pages)}  "
                            f"**Root pages:** {len(roots)}\n\n"
                        )
                        f.write(summary)
                        print_section(summary.strip())
                        logging.info(summary.strip())
                        # --- Metadata Table ---
                        f.write("## 📊 Page Metadata Table\n\n")
                        headers = [
                            "ID", "Title", "URL", "Created", "Updated", "Last Viewed", "Version", "Comments", "Attachments", "Parent ID", "Ancestor IDs"
                        ]
                        f.write("| " + " | ".join(f"**{h}**" for h in headers) + " |\n")
                        f.write("|" + "---|" * len(headers) + "\n")
                        for pid, meta in page_metadata.items():
                            title = meta.get('title') or next((p['title'] for p in filtered_pages if p['id'] == pid), 'Untitled')
                            url = f"[{title}](https://{base_url.split('//')[-1]}/pages/{pid})"
                            created = meta.get('created', 'N/A')
                            updated = meta.get('updated', 'N/A')
                            last_viewed = meta.get('last_viewed', 'N/A')
                            version = meta.get('version', 'N/A')
                            comments = meta.get('num_comments', 0)
                            attachments = meta.get('num_attachments', 0)
                            parent_id = meta.get('parent_id', 'N/A')
                            ancestor_ids = ','.join(str(a) for a in meta.get('ancestor_ids', []))
                            row = [
                                pid,
                                title,
                                url,
                                created,
                                updated,
                                last_viewed,
                                str(version),
                                str(comments),
                                str(attachments),
                                str(parent_id),
                                ancestor_ids
                            ]
                            f.write("| " + " | ".join(row) + " |\n")
                        f.write("\n---\n\n")
                        f.write("## Table of Contents\n" + '\n'.join(toc) + '\n---\n')
                        for root in roots:
                            write_tree_md(f, root)
                    print_section(f"Space structure report written to {report_path}. Crawl complete!")
                    logging.info(f"Space structure report written to {report_path}")
                # Update report (JSON)
                if output_format in ('json', 'both'):
                    json_tree = [build_json_tree(root) for root in roots if build_json_tree(root)]
                    with open(json_path, "w", encoding="utf-8") as jf:
                        json.dump(json_tree, jf, indent=2)
                    print_section(f"JSON structure report written to {json_path}. Crawl complete!")
                    logging.info(f"JSON structure report written to {json_path}")
                # Feedback
                batch_time = time.time() - batch_start
                batch_times.append(batch_time)
                elapsed = time.time() - start_time
                remaining = len(all_page_ids) - processed_count
                avg_batch_time = sum(batch_times) / len(batch_times) if batch_times else 0
                avg_page_time = (sum(batch_times) / (processed_count or 1)) if processed_count else 0
                eta_batches = avg_batch_time * (math.ceil(remaining / batch_size))
                eta_pages = avg_page_time * remaining
                print_section(f"Processed {processed_count}/{len(all_page_ids)}. Remaining: {remaining}. Batch time: {batch_time:.1f}s. ETA: {eta_batches/60:.1f} min (batch), {eta_pages/60:.1f} min (page). Successes: {successes}, Failures: {failures}")
                # Show a mini tree preview (up to 10 lines, 2 levels deep)
                preview_lines = []
                for root in roots:
                    preview_lines += print_tree_preview(root, max_depth=2, max_lines=10-len(preview_lines))
                    if len(preview_lines) >= 10:
                        break
                print("\n".join(preview_lines))
                to_process = [pid for pid in all_page_ids if pid not in processed_ids]
            if output_format in ('md', 'both'):
                print_section(f"Space structure report written to {report_path}. Crawl complete!")
            if output_format in ('json', 'both'):
                print_section(f"JSON structure report written to {json_path}. Crawl complete!")
    except KeyboardInterrupt:
        print_section("Crawl interrupted. Progress saved. You can resume by running again.")
        return

def download_pages_concurrent(pages, output_dir, dry_run=False):
    """Download pages concurrently with tqdm progress bar and dry run support, with spinner for each file."""
    if not pages:
        print_section("No pages to download.")
        logging.warning("No pages to download.")
        return
    failed = []
    total = len(pages)
    print_section(f"Starting download of {total} pages...")
    existing_files = set()
    for root, _, files in os.walk(output_dir):
        for f in files:
            existing_files.add(os.path.join(root, f))

    # Find which files would be overwritten
    files_to_overwrite = []
    for page in pages:
        title = page.get('title', 'Untitled')
        ancestors = page.get('ancestors', [])
        path_parts = [sanitize_filename(a.get('title', '')) for a in ancestors if a.get('title')]
        dir_path = os.path.join(output_dir, *path_parts) if path_parts else output_dir
        filename = sanitize_filename(title) + ".md"
        filepath = os.path.join(dir_path, filename)
        if os.path.exists(filepath):
            files_to_overwrite.append(filepath)

    # Batch overwrite/skip/increment prompt
    if files_to_overwrite and not dry_run:
        print_section(f"Warning: {len(files_to_overwrite)} files would be overwritten in {output_dir}.")
        print("First 5:")
        for fp in files_to_overwrite[:5]:
            print(f"  - {fp}")
        print("...") if len(files_to_overwrite) > 5 else None
        batch_mode = prompt_with_validation(
            "What would you like to do when existing files are found?",
            valid_options=['1. Overwrite all existing files (recommended for most cases).',
                          '2. Skip all existing files.',
                          '3. Decide for each file interactively.',
                          '4. Increment all file names (never overwrite, always create new)'],
            default='1. Overwrite all existing files (recommended for most cases).'
        )
        batch_mode = {'1': 'a', '2': 's', '3': 'i', '4': 'increment'}[batch_mode[0]]
    else:
        batch_mode = 'a'
    overwrite_mode = {'mode': 'all' if batch_mode == 'a' else 'skip' if batch_mode == 's' else 'ask' if batch_mode == 'i' else 'increment'}

    if dry_run:
        for page in tqdm(pages, desc="[DRY RUN] Would save"):
            title = page.get('title', 'Untitled')
            filename = sanitize_filename(title) + ".txt"
            filename = unique_filename(filename, output_dir, dir_path)
            filepath = os.path.join(output_dir, filename)
            print(f"[DRY RUN] Would save: {filepath}")
    else:
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(save_page, page, output_dir, overwrite_mode): page for page in pages}
            for future in tqdm(as_completed(futures), total=total, desc="Downloading pages"):
                page = futures[future]
                try:
                    with spinner(f"Saving: {page.get('title', 'Untitled')}") as spin:
                        if not future.result():
                            failed.append(page.get('title', 'Untitled'))
                except Exception as e:
                    print_section(f"Error downloading {page.get('title', 'Untitled')}: {e}")
                    logging.error(f"Download error for '{page.get('title', 'Untitled')}': {e}")
                    failed.append(page.get('title', 'Untitled'))
        if failed:
            print_section(f"Failed to save {len(failed)} pages:")
            for title in failed:
                print(f"  - {title}")
            logging.warning(f"Failed to save {len(failed)} pages: {failed}")
    print_section(f"Download complete. {total} pages processed, {len(failed)} errors.")
    logging.info(f"Download complete. {total} pages processed, {len(failed)} errors.")

def write_metrics_md(pages, output_dir, mode, parent_title=None):
    """Write a Markdown metrics report for the downloaded pages, with beautified status messages."""
    if not pages:
        print_section("No pages to write metrics for.")
        return
    os.makedirs(output_dir, exist_ok=True)
    metrics_path = os.path.join(output_dir, "metrics.md")
    try:
        with open(metrics_path, "w", encoding="utf-8") as f:
            now = datetime.now(timezone.utc)
            stale_threshold = timedelta(days=365)
            fresh_threshold = timedelta(days=30)
            f.write(f"# Confluence Page Metrics\n\n")
            if mode == '1':
                f.write(f"**Number of pages in space:** {len(pages)}\n\n")
            else:
                f.write(f"**Number of pages under parent page{' ('+parent_title+')' if parent_title else ''}:** {len(pages)}\n\n")
            f.write("| Page Title | Created | Last Updated | Last Viewed | Last Updated By |\n")
            f.write("|---|---|---|---|---|\n")
            for page in pages:
                title_raw = page.get('title', 'Untitled').replace('|', '\\|').replace('\n',' ')
                created = page.get('history', {}).get('createdDate') or page.get('version', {}).get('when')
                updated = page.get('version', {}).get('when')
                updated_by = page.get('version', {}).get('by', {}).get('displayName', 'Unknown').replace('|', '\\|')
                last_viewed = page.get('history', {}).get('lastViewed', {}).get('when')
                created_dt = updated_dt = last_viewed_dt = None
                try:
                    if created:
                        created_dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
                    if updated:
                        updated_dt = datetime.fromisoformat(updated.replace('Z', '+00:00'))
                    if last_viewed:
                        last_viewed_dt = datetime.fromisoformat(last_viewed.replace('Z', '+00:00'))
                except Exception:
                    pass
                # Color title based on last viewed
                title = title_raw
                if last_viewed_dt:
                    days_since_view = (now - last_viewed_dt).days
                    if days_since_view > 365:
                        title = f'<span style="color:red">{title_raw}</span>'
                    elif days_since_view < 30:
                        title = f'<span style="color:green">{title_raw}</span>'
                bold = updated_dt and (now - updated_dt) > stale_threshold
                if bold:
                    title = f'**{title}**'
                row = (
                    f"{title} | "
                    f"{created_dt.date() if created_dt else created or ''} | "
                    f"{updated_dt.date() if updated_dt else updated or ''} | "
                    f"{last_viewed_dt.date() if last_viewed_dt else last_viewed or ''} | "
                    f"{updated_by}"
                )
                f.write(row + "\n")
        print_section(f"Metrics written to {metrics_path}")
    except Exception as e:
        print_section(f"Error writing metrics file: {e}")
        logging.error(f"Error writing metrics file: {e}")

# === Main Script ===
if __name__ == "__main__":
    # Legacy main() call is replaced by the new CLI menu
    # main()
    # Setup base_url and auth as in main()
    args = get_args()
    base_url = args.base_url or get_env_or_prompt(
        'CONFLUENCE_BASE_URL',
        'Confluence base URL',
        default='https://avetta.atlassian.net/wiki',
        stub_values=['https://your-domain.atlassian.net/wiki', '', None]
    )
    if not base_url.startswith("http://") and not base_url.startswith("https://"):
        base_url = "https://" + base_url
    username = args.username or get_env_or_prompt(
        'CONFLUENCE_USERNAME',
        'Confluence username/email',
        stub_values=['your.email@example.com', '', None]
    )
    api_token_cli = getattr(args, 'api_token', None)
    api_token_env = os.getenv('CONFLUENCE_API_TOKEN')
    api_token = get_env_or_prompt(
        'CONFLUENCE_API_TOKEN',
        'Confluence API token',
        is_secret=True,
        stub_values=['your-api-token-here', '', None]
    )
    auth = (username, api_token)
    run_cli_main_menu(base_url, auth)
