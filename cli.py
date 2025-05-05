"""
cli.py
-------
Handles all user interaction, argument parsing, and the CLI entry point for the Confluence Downloader project.
All prompts, printing, and user-facing output are centralized here.
"""
from main import main
from constants import BATCH_PROMPT, USER_PROMPT_OVERWRITE
from argparse import ArgumentParser

def get_args():
    parser = ArgumentParser(description="Confluence Downloader")
    parser.add_argument('--base-url', help='Confluence base URL')
    parser.add_argument('--username', help='Confluence username/email')
    parser.add_argument('--mode', choices=['1', '2'], help='1: entire space, 2: by parent page')
    parser.add_argument('--output-dir', help='Output directory')
    parser.add_argument('--metrics-only', action='store_true', help='Generate metrics report only')
    parser.add_argument('--parent-url', help='Parent page URL (for mode 2)')
    parser.add_argument('--space-key', help='Space key (for mode 1)')
    parser.add_argument('--dry-run', action='store_true', help='Dry run mode')
    parser.add_argument('--version', action='version', version='%(prog)s 1.0.0', help='Show version and exit')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose (DEBUG) logging')
    return parser.parse_args()

def prompt_with_validation(prompt: str, valid_options=None, default=None, allow_blank=False) -> str:
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
        print(f"Invalid selection. Please enter one of: {', '.join(valid_options)}")

def run():
    args = get_args()
    result = main(args)
    # Print config summary
    print("\nConfiguration:")
    for k, v in result['config'].items():
        print(f"  {k}: {v}")
    print(f"\nStatus: {result['status']}")
    print(result['message'])

if __name__ == "__main__":
    run() 