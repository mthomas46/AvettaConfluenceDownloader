"""
cli.py
-------
Handles all user interaction, argument parsing, and the CLI entry point for the Confluence Downloader project.
All prompts, printing, and user-facing output are centralized here.
"""
from main import main
from constants import BATCH_PROMPT, USER_PROMPT_OVERWRITE, Mode
from argparse import ArgumentParser
import sys
from colorama import Fore, Style
import logging

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
    parser.add_argument('--dry-run', action='store_true', default=None, help='Preview actions without writing files')
    parser.add_argument('--llm-combine', action='store_true', help='Combine downloaded files using an LLM and save the result')
    parser.add_argument('--llm-model', choices=['gpt-3.5-turbo'], default=None, help='OpenAI LLM model to use for combining files (default: gpt-3.5-turbo)')
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
    Main CLI flow: prompts the user for all required options, shows a summary, and displays results.
    Handles all user interaction and output for the Confluence Downloader.
    """
    args = get_args()

    # Prompt for mode if not provided
    if not args.mode:
        print(f"{Fore.CYAN}\n=== Download Mode Selection ===\n{Style.RESET_ALL}")
        args.mode = prompt_with_validation(
            f"{Fore.YELLOW}Select download mode:\n  1. Download entire space\n  2. Download by parent page\n\nEnter 1 or 2{Style.RESET_ALL}",
            valid_options=['1', '2'],
            default='2'
        )

    # Prompt for parent URL if mode 2 and not provided
    if args.mode == '2' and not args.parent_url:
        print(f"{Fore.CYAN}\n=== Parent Page Selection ===\n{Style.RESET_ALL}")
        default_parent_url = "https://avetta.atlassian.net/wiki/spaces/it/pages/1122336779"
        entered_url = input(f"{Fore.YELLOW}Enter parent page URL\n[default: {default_parent_url}]: {Style.RESET_ALL}").strip()
        args.parent_url = entered_url or default_parent_url

    # Prompt for dry run if not set via CLI
    if args.dry_run is None:
        print(f"{Fore.CYAN}\n=== Dry Run Option ===\n{Style.RESET_ALL}")
        dry_run_input = prompt_with_validation(
            f"{Fore.YELLOW}Run in dry run mode? (no files will be written) (y/n){Style.RESET_ALL}",
            valid_options=['y', 'n'],
            default='n'
        )
        args.dry_run = (dry_run_input == 'y')

    # Prompt for overwrite options if not dry-run or metrics-only
    if not args.dry_run and not args.metrics_only:
        print(f"{Fore.CYAN}\n=== Overwrite Options ===\n{Style.RESET_ALL}")
        overwrite_choice = prompt_with_validation(
            f"{Fore.YELLOW}{BATCH_PROMPT}\nEnter 1, 2, 3, or 4{Style.RESET_ALL}",
            valid_options=['1', '2', '3', '4'],
            default='1'
        )
        # Map user choice to a string for main()
        overwrite_map = {'1': 'overwrite', '2': 'skip', '3': 'ask', '4': 'increment'}
        args.overwrite_mode = overwrite_map[overwrite_choice]
    else:
        args.overwrite_mode = 'overwrite'

    # Print summary and confirm
    print(f"{Fore.CYAN}\n=== Summary of Selected Options ==={Style.RESET_ALL}")
    print(f"  Mode: {args.mode}")
    if args.mode == '2':
        print(f"  Parent URL: {args.parent_url}")
    print(f"  Dry Run: {args.dry_run}")
    print(f"  Overwrite Mode: {args.overwrite_mode}")
    print(f"  Metrics Only: {args.metrics_only}")
    print(f"  Output Directory: {args.output_dir or 'confluence_pages'}")
    print(f"  Verbose: {args.verbose}")
    confirm = input(f"{Fore.YELLOW}\nProceed with these settings? (y/n) [default: y]: {Style.RESET_ALL}").strip().lower() or 'y'
    if confirm != 'y':
        print(f"{Fore.RED}Aborted by user.{Style.RESET_ALL}")
        sys.exit(0)

    print(f"{Fore.CYAN}\n=== Starting Download Process ===\n{Style.RESET_ALL}")
    result = main(args)
    # Print config summary
    config_lines = ["\nConfiguration:"]
    for option_name, option_value in result['config'].items():
        config_lines.append(f"  {option_name}: {option_value}")
    config_lines.append(f"\nStatus: {result['status']}")
    config_lines.append(result['message'])
    print('\n'.join(config_lines))

    # Print selected options
    if 'selected_options' in result:
        selected_lines = [f"\n{Fore.CYAN}=== Selected Options ==={Style.RESET_ALL}"]
        for option_name, option_value in result['selected_options'].items():
            selected_lines.append(f"  {option_name}: {option_value}")
        print('\n'.join(selected_lines))

    # Print downloaded files
    if 'downloaded_files' in result:
        if result['downloaded_files']:
            files_section = [f"\n{Fore.CYAN}=== Downloaded Files ==={Style.RESET_ALL}"]
            files_section += [f"  {file_path}" for file_path in result['downloaded_files']]
            print('\n'.join(files_section))
        else:
            print(f"\n{Fore.CYAN}=== Downloaded Files ==={Style.RESET_ALL}\n  (No files were downloaded.)")

    # LLM combine option: skip if metrics-only or no files downloaded
    if args.metrics_only:
        print(f"{Fore.YELLOW}Metrics-only mode: LLM combine is not available because no files were downloaded.{Style.RESET_ALL}")
        return
    if not result.get('downloaded_files') or not result['downloaded_files']:
        print(f"{Fore.YELLOW}No files were downloaded, so LLM combine is not available.{Style.RESET_ALL}")
        return

    # LLM combine option: prompt user if not set via CLI
    llm_combine = getattr(args, 'llm_combine', False)
    llm_model = getattr(args, 'llm_model', None)
    if not llm_combine:
        print(f"\n{Fore.CYAN}=== LLM Combine Option ==={Style.RESET_ALL}")
        llm_combine_input = prompt_with_validation(
            f"{Fore.YELLOW}Combine downloaded files into one using an LLM? (y/n){Style.RESET_ALL}",
            valid_options=['y', 'n'],
            default='n'
        )
        llm_combine = (llm_combine_input == 'y')
    if llm_combine and not llm_model:
        print(f"\n{Fore.CYAN}=== LLM Model Selection ==={Style.RESET_ALL}")
        llm_model = prompt_with_validation(
            f"{Fore.YELLOW}Select OpenAI model for combining files (default: gpt-3.5-turbo):\n  1. gpt-3.5-turbo{Style.RESET_ALL}",
            valid_options=['1'],
            default='1'
        )
        llm_model = 'gpt-3.5-turbo'  # Only one free model for now
    if llm_combine:
        from llm_utils import combine_files_with_llm
        import os
        openai_api_key = os.getenv('OPENAI_API_KEY')
        if not openai_api_key:
            print(f"{Fore.RED}OPENAI_API_KEY not set in environment. Skipping LLM combine step.{Style.RESET_ALL}")
        else:
            logging.basicConfig(level=logging.INFO)
            logger = logging.getLogger("llm_combine")
            print(f"\n{Fore.CYAN}=== LLM Combining Files ==={Style.RESET_ALL}")
            logger.info("Starting LLM combine process.")
            print(f"{Fore.YELLOW}Preparing files for LLM...{Style.RESET_ALL}")
            logger.debug(f"Files to combine: {result['downloaded_files']}")
            # Use parent page name for output file if available
            parent_name = None
            if 'selected_options' in result and 'parent_url' in result['selected_options']:
                parent_url = result['selected_options']['parent_url']
                # Try to extract a name from the parent_url
                import re
                match = re.search(r'/pages/\d+/([^/]+)$', parent_url)
                if match:
                    parent_name = match.group(1).replace('+', '_').replace('-', '_')
            if not parent_name:
                parent_name = 'ParentPage'
            output_filename = f"LLM_Combined_{parent_name}.md"
            print(f"{Fore.YELLOW}Calling LLM to combine files... This may take a while.{Style.RESET_ALL}")
            logger.info(f"Calling OpenAI LLM with model: {llm_model or 'gpt-3.5-turbo'}")
            llm_output_path = combine_files_with_llm(
                result['downloaded_files'],
                args.output_dir or 'confluence_pages',
                openai_api_key,
                model=llm_model or 'gpt-3.5-turbo',
                output_filename=output_filename
            )
            if llm_output_path:
                print(f"{Fore.GREEN}LLM-combined file saved to: {llm_output_path}{Style.RESET_ALL}")
                logger.info(f"LLM-combined file saved to: {llm_output_path}")
            else:
                print(f"{Fore.RED}LLM combine failed. See logs for details.{Style.RESET_ALL}")
                logger.error("LLM combine failed. No output file was created.")

if __name__ == "__main__":
    run() 