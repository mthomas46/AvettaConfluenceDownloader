"""
args.py
-------
Argument parsing for the Confluence Downloader CLI.
"""
from argparse import ArgumentParser, Namespace
from constants import Mode

def get_args() -> Namespace:
    """
    Parse command-line arguments for the Confluence Downloader CLI.
    Returns:
        argparse.Namespace: Parsed arguments.
    """
    parser = ArgumentParser(description="Confluence Downloader")
    parser.add_argument('--base-url', help='Confluence base URL (e.g., https://your-domain.atlassian.net/wiki)')
    parser.add_argument('--username', help='Confluence username/email (e.g., your.email@example.com)')
    parser.add_argument('--mode', choices=[m.value for m in Mode], help='1: entire space, 2: by parent page')
    parser.add_argument('--output-dir', help='Output directory for downloaded files')
    parser.add_argument('--metrics-only', action='store_true', help='Only generate metrics report (no page downloads)')
    parser.add_argument('--parent-url', help='Parent page URL (for mode 2)')
    parser.add_argument('--space-key', help='Space key (for mode 1)')
    parser.add_argument('--dry-run', action='store_true', default=None, help='Preview actions without writing files')
    parser.add_argument('--llm-combine', action='store_true', help='Combine downloaded files using an LLM and save the result')
    parser.add_argument('--llm-model',
        choices=['gpt-3.5-turbo', 'gpt-4-1106-preview', 'gpt-4o', 'claude-3.5-sonnet'],
        default='gpt-3.5-turbo',
        help='LLM model to use for combining files (default: gpt-3.5-turbo). gpt-4.1, gpt-4o, and Claude 3.5 Sonnet are not free.')
    parser.add_argument('--llm-overwrite-mode', choices=['overwrite', 'increment'], default='overwrite', help='LLM combine file overwrite mode: overwrite (default) or increment (add number if file exists)')
    parser.add_argument('--version', action='version', version='%(prog)s 1.0.0', help='Show version and exit')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose (DEBUG) logging')
    return parser.parse_args() 