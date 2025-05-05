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
    parser.add_argument('--mode', choices=['1', '2'], help='1: entire space, 2: by parent page')
    parser.add_argument('--output-dir', help='Output directory')
    parser.add_argument('--metrics-only', action='store_true', help='Generate metrics report only')
    parser.add_argument('--parent-url', help='Parent page URL (for mode 2)')
    parser.add_argument('--space-key', help='Space key (for mode 1)')
    parser.add_argument('--dry-run', action='store_true', help='Dry run mode')
    parser.add_argument('--version', action='version', version=f'%(prog)s {__version__}', help='Show version and exit')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose (DEBUG) logging')
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

def prompt_with_validation(prompt: str, valid_options=None, default=None, allow_blank=False) -> str:
    """
    Prompt the user for input, validate against valid_options, and handle defaults.
    """
    while True:
        if default is not None:
            user_input = input(f"{prompt} [default: {default}]: ").strip()
            if not user_input:
                user_input = default
        else:
            user_input = input(f"{prompt}: ").strip()
        if allow_blank and user_input == '':
            return user_input
        if valid_options is None or user_input in valid_options:
            return user_input
        print(f"{Fore.RED}Invalid selection. Please enter one of: {', '.join(valid_options)}{Style.RESET_ALL}")

# === Download and Progress ===
def download_pages_concurrent(pages, output_dir, dry_run=False):
    """Download pages concurrently with tqdm progress bar and dry run support."""
    if not pages:
        print(f"{Fore.YELLOW}No pages to download.{Style.RESET_ALL}")
        logging.warning("No pages to download.")
        return
    failed = []
    total = len(pages)
    print(f"\nStarting download of {total} pages...")
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
        print(f"{Fore.YELLOW}Warning: {len(files_to_overwrite)} files would be overwritten in {output_dir}.{Style.RESET_ALL}")
        print("First 5:")
        for fp in files_to_overwrite[:5]:
            print(f"  - {fp}")
        print("...") if len(files_to_overwrite) > 5 else None
        batch_mode = prompt_with_validation(
            "\nWhat would you like to do when existing files are found?\n  1. Overwrite all existing files (recommended for most cases).\n  2. Skip all existing files.\n  3. Decide for each file interactively.\n  4. Increment all file names (never overwrite, always create new)",
            valid_options={'1', '2', '3', '4'},
            default='1'
        )
        batch_mode = {'1': 'a', '2': 's', '3': 'i', '4': 'increment'}[batch_mode]
    else:
        batch_mode = 'a'
    overwrite_mode = {'mode': 'all' if batch_mode == 'a' else 'skip' if batch_mode == 's' else 'ask' if batch_mode == 'i' else 'increment'}

    if dry_run:
        for page in tqdm(pages, desc="[DRY RUN] Would save"):
            title = page.get('title', 'Untitled')
            filename = sanitize_filename(title) + ".txt"
            filename = unique_filename(filename, output_dir, dir_path)
            filepath = os.path.join(output_dir, filename)
            print(f"{Fore.BLUE}[DRY RUN]{Style.RESET_ALL} Would save: {Fore.GREEN}{filepath}{Style.RESET_ALL}")
    else:
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(save_page, page, output_dir, overwrite_mode): page for page in pages}
            for future in tqdm(as_completed(futures), total=total, desc="Downloading pages"):
                page = futures[future]
                try:
                    if not future.result():
                        failed.append(page.get('title', 'Untitled'))
                except Exception as e:
                    print(f"\n{Fore.RED}Error downloading {page.get('title', 'Untitled')}: {e}{Style.RESET_ALL}")
                    logging.error(f"Download error for '{page.get('title', 'Untitled')}': {e}")
                    failed.append(page.get('title', 'Untitled'))
        if failed:
            print(f"\n{Fore.RED}Failed to save {len(failed)} pages:{Style.RESET_ALL}")
            for title in failed:
                print(f"  - {title}")
            logging.warning(f"Failed to save {len(failed)} pages: {failed}")
    print(f"\n{Fore.GREEN}Download complete. {total} pages processed, {len(failed)} errors.{Style.RESET_ALL}")
    logging.info(f"Download complete. {total} pages processed, {len(failed)} errors.")

# === Metrics Report ===
def write_metrics_md(pages, output_dir, mode, parent_title=None):
    """Write a Markdown metrics report for the downloaded pages."""
    if not pages:
        print(f"{Fore.YELLOW}No pages to write metrics for.{Style.RESET_ALL}")
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
        print(f"{Fore.GREEN}Metrics written to {metrics_path}{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}Error writing metrics file: {e}{Style.RESET_ALL}")
        logging.error(f"Error writing metrics file: {e}")

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

# === Main Script ===
def main():
    """Main entry point for the script."""
    args = get_args()
    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        print(f"{Fore.YELLOW}Verbose logging enabled (DEBUG level).{Style.RESET_ALL}")
    else:
        logging.getLogger().setLevel(logging.INFO)
    print(f"{Fore.CYAN}\n==== Confluence Downloader v{__version__} ===={Style.RESET_ALL}")
    dry_run = args.dry_run
    if not args.dry_run:
        print(f"{Fore.MAGENTA}Would you like to run in dry run mode? (Preview actions, no files will be written){Style.RESET_ALL}")
        dry = input("Dry run? (y/n) [default: n]: ").strip().lower() or 'n'
        if dry == 'y':
            dry_run = True
            print(f"{Fore.MAGENTA}Dry run mode enabled. No files will be written.{Style.RESET_ALL}")

    # Use .env values or prompt as needed
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
    # Warn if API token is passed as a CLI argument (security)
    api_token_cli = getattr(args, 'api_token', None)
    api_token_env = os.getenv('CONFLUENCE_API_TOKEN')
    api_token = get_env_or_prompt(
        'CONFLUENCE_API_TOKEN',
        'Confluence API token',
        is_secret=True,
        stub_values=['your-api-token-here', '', None]
    )
    if api_token_cli:
        print(f"{Fore.RED}Warning: Passing API token as a command-line argument may expose it in process lists! Use .env or interactive prompt instead.{Style.RESET_ALL}")
    auth = (username, api_token)

    # Print config summary (mask API token)
    print(f"\n{Fore.CYAN}Configuration:{Style.RESET_ALL}")
    print(f"  Base URL: {base_url}")
    print(f"  Username: {username}")
    print(f"  API Token: {mask_token(api_token)}")
    print(f"  Output Dir: {args.output_dir or os.getenv('OUTPUT_DIR', 'confluence_pages')}")
    print(f"  Mode: {args.mode or 'prompt'}")
    print(f"  Metrics Only: {args.metrics_only}")
    print(f"  Dry Run: {dry_run}")
    print(f"  Verbose: {args.verbose}")

    # Page selection
    if args.mode:
        mode = args.mode
    else:
        print("\nHow would you like to select Confluence pages?")
        print("  1. Download all pages in an entire space (may be very large).\n")
        print("  2. Download all pages under a specific parent page (recommended for smaller sets).\n")
        print("  3. Search and download by page title.\n")
        while True:
            mode = input("Enter 1 for entire space, 2 for parent page, or 3 for search by title [default: 2]: ").strip() or '2'
            if mode in {'1', '2', '3'}:
                break
            print(f"{Fore.RED}Invalid selection. Please enter 1, 2, or 3.{Style.RESET_ALL}")
            logging.warning(f"Invalid mode selection: {mode}")

    output_dir = args.output_dir or get_env_or_prompt(
        'OUTPUT_DIR',
        'Output directory',
        default='confluence_pages',
        stub_values=['confluence_pages', '', None]
    )

    print(f"\n{Fore.CYAN}---- Output Options ----{Style.RESET_ALL}")
    if args.metrics_only:
        metrics_only = True
    else:
        print("\nWhat would you like to do?")
        print("  1. Generate a metrics report only as a Markdown file.\n")
        print("  2. Generate a metrics report as a Markdown file AND download all pages as text files.\n")
        while True:
            metrics_mode = input("Enter 1 for metrics only, or 2 for metrics and files [default: 2]: ").strip() or '2'
            if metrics_mode in {'1', '2'}:
                metrics_only = metrics_mode == '1'
                break
            print(f"{Fore.RED}Invalid selection. Please enter 1 or 2.{Style.RESET_ALL}")
            logging.warning(f"Invalid metrics_mode selection: {metrics_mode}")

    try:
        if mode == '1':
            print(f"\n{Fore.YELLOW}WARNING: Downloading an entire Confluence space may take a long time and generate a large number of files.{Style.RESET_ALL}")
            confirm = input("Are you sure you want to proceed? (y/n) [default: n]: ").strip().lower() or 'n'
            if confirm != 'y':
                print(f"{Fore.CYAN}Aborted.{Style.RESET_ALL}")
                logging.info("User aborted entire space download at confirmation.")
                return
            confirm2 = input("Really proceed? (y/n) [default: n]: ").strip().lower() or 'n'
            if confirm2 != 'y':
                print(f"{Fore.CYAN}Aborted.{Style.RESET_ALL}")
                logging.info("User aborted entire space download at double confirmation.")
                return
            space_key = args.space_key or input("Enter space key (e.g. DEV): ").strip()
            print(f"\n{Fore.CYAN}Fetching pages from space '{space_key}'...{Style.RESET_ALL}")
            pages = get_all_pages_in_space(base_url, auth, space_key)
            print(f"{Fore.CYAN}Found {len(pages)} pages in space '{space_key}'.{Style.RESET_ALL}")
            write_metrics_md(pages, output_dir, mode)
            if not metrics_only:
                download_pages_concurrent(pages, output_dir, dry_run=dry_run)
                # Optional: Consolidate markdown files
                do_consolidate = input("\nWould you like to generate a consolidated Markdown file from all downloaded pages? (y/n) [default: n]: ").strip().lower() or 'n'
                if do_consolidate == 'y':
                    consolidate_markdown_files(output_dir)
            print(f"\n{Fore.GREEN}Summary: {len(pages)} pages processed. Metrics written to {output_dir}/metrics.md{Style.RESET_ALL}")
        elif mode == '3':
            search_term = input("Enter title search term: ").strip()
            pages = search_pages_by_title(base_url, auth, search_term)
            if not pages:
                print(f"{Fore.RED}No pages found matching '{search_term}'.{Style.RESET_ALL}")
                logging.info(f"No pages found for search term: {search_term}")
                return
            print(f"{Fore.CYAN}Found {len(pages)} matching pages:{Style.RESET_ALL}")
            for idx, page in enumerate(pages, 1):
                print(f"  {idx}. {page.get('title', 'Untitled')} (ID: {page.get('id')})")
            while True:
                selection = input("Enter comma-separated numbers to download (or 'all' for all, default: all): ").strip()
                if not selection or selection.lower() == 'all':
                    selected_pages = pages
                    break
                try:
                    indices = [int(i)-1 for i in selection.split(',') if i.strip().isdigit()]
                    if not indices or any(i < 0 or i >= len(pages) for i in indices):
                        raise ValueError
                    selected_pages = [pages[i] for i in indices]
                    break
                except Exception:
                    print(f"{Fore.RED}Invalid selection. Please enter valid numbers or 'all'.{Style.RESET_ALL}")
                    logging.warning(f"Invalid page selection: {selection}")
            write_metrics_md(selected_pages, output_dir, mode)
            if not metrics_only:
                download_pages_concurrent(selected_pages, output_dir, dry_run=dry_run)
            print(f"\n{Fore.GREEN}Summary: {len(selected_pages)} pages processed. Metrics written to {output_dir}/metrics.md{Style.RESET_ALL}")
        else:
            default_parent_url = "https://avetta.atlassian.net/wiki/spaces/it/pages/1122336779"
            page_url = args.parent_url or input(f"Enter parent page URL [default: {default_parent_url}]: ").strip() or default_parent_url
            page_id = get_page_id_from_url(page_url, base_url, auth)
            if not page_id:
                print(f"{Fore.RED}Could not extract pageId from URL. Please provide a valid Confluence page URL containing pageId.{Style.RESET_ALL}")
                logging.error(f"Could not extract pageId from URL: {page_url}")
                return
            print(f"\n{Fore.CYAN}Fetching pages under parent page...{Style.RESET_ALL}")
            pages = get_descendants(base_url, auth, page_id)
            if not pages:
                print(f"{Fore.RED}\nNo pages could be retrieved. This is usually due to insufficient permissions or a private page.\nPlease check your Confluence permissions, try a different parent page, or contact your Confluence administrator.{Style.RESET_ALL}")
                logging.warning(f"No pages retrieved for parent page: {page_url}")
                retry = input("Would you like to try a different parent page or credentials? (y/n) [default: n]: ").strip().lower() or 'n'
                if retry == 'y':
                    print(f"{Fore.CYAN}Restart the script and try again with a different page or credentials.{Style.RESET_ALL}")
                return
            parent_title = pages[0].get('title') if pages else None
            print(f"{Fore.CYAN}Found {len(pages)} pages under parent page.{Style.RESET_ALL}")
            write_metrics_md(pages, output_dir, mode, parent_title)
            if not metrics_only:
                download_pages_concurrent(pages, output_dir, dry_run=dry_run)
            print(f"\n{Fore.GREEN}Summary: {len(pages)} pages processed. Metrics written to {output_dir}/metrics.md{Style.RESET_ALL}")
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Operation cancelled by user. Exiting gracefully.{Style.RESET_ALL}")
        logging.info("Operation cancelled by user via KeyboardInterrupt.")
        return

if __name__ == "__main__":
    main()
