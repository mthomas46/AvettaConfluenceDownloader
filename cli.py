"""
cli.py
-------
Handles all user interaction, argument parsing, and the CLI entry point for the Confluence Downloader project.
All prompts, printing, and user-facing output are centralized here.
"""
from main import main
from constants import BATCH_PROMPT, USER_PROMPT_OVERWRITE, Mode
from argparse import ArgumentParser

def get_args():
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
    parser.add_argument('--dry-run', action='store_true', help='Preview actions without writing files')
    parser.add_argument('--version', action='version', version='%(prog)s 1.0.0', help='Show version and exit')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose (DEBUG) logging')
    return parser.parse_args()

def prompt_with_validation(prompt: str, valid_options=None, default=None, allow_blank=False) -> str:
    """
    Prompt the user for input with optional validation and default value.
    Args:
        prompt (str): The prompt message.
        valid_options (list, optional): List of valid options. Defaults to None.
        default (str, optional): Default value if input is blank. Defaults to None.
        allow_blank (bool, optional): Allow blank input. Defaults to False.
    Returns:
        str: The validated user input.
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
        print(f"Invalid selection. Please enter one of: {', '.join(valid_options)}")

def run():
    """
    Run the CLI: parse arguments, invoke main workflow, and print results.
    """
    args = get_args()
    # Prompt for mode if not provided
    if not args.mode:
        args.mode = prompt_with_validation(
            "Select download mode:\n  1. Download entire space\n  2. Download by parent page\nEnter 1 or 2",
            valid_options=['1', '2'],
            default='2'
        )
    # Prompt for parent URL if mode 2 and not provided
    if args.mode == '2' and not args.parent_url:
        default_parent_url = "https://avetta.atlassian.net/wiki/spaces/it/pages/1122336779"
        entered_url = input(f"Enter parent page URL [default: {default_parent_url}]: ").strip()
        args.parent_url = entered_url or default_parent_url
    result = main(args)
    # Print config summary
    print("\nConfiguration:")
    for k, v in result['config'].items():
        print(f"  {k}: {v}")
    print(f"\nStatus: {result['status']}")
    print(result['message'])

if __name__ == "__main__":
    run() 