"""
cli.py
-------
Handles all user interaction, argument parsing, and the CLI entry point for the Confluence Downloader project.
All prompts, printing, and user-facing output are centralized here.
"""
from main import main
from constants import BATCH_PROMPT, USER_PROMPT_OVERWRITE, Mode, DEFAULT_BASE_URL, DEFAULT_OUTPUT_DIR, STUB_EMAIL
from argparse import ArgumentParser
import sys
from colorama import Fore, Style
import logging
import yaml
import re
import os
import pprint
from log_parser import search_logs

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
    parser.add_argument('--llm-model',
        choices=['gpt-3.5-turbo', 'gpt-4-1106-preview', 'gpt-4o', 'claude-3.5-sonnet'],
        default='gpt-3.5-turbo',
        help='LLM model to use for combining files (default: gpt-3.5-turbo). gpt-4.1, gpt-4o, and Claude 3.5 Sonnet are not free.')
    parser.add_argument('--llm-overwrite-mode', choices=['overwrite', 'increment'], help='LLM combine file overwrite mode: overwrite or increment (add number if file exists)')
    parser.add_argument('--version', action='version', version='%(prog)s 1.0.0', help='Show version and exit')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose (DEBUG) logging')
    parser.add_argument('--parse-logs', action='store_true', help='Parse and search logs using the built-in log parser')
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
    # Main feature selection menu
    print(f"{Fore.CYAN}\n=== Main Menu ==={Style.RESET_ALL}")
    while True:
        main_choice = prompt_with_validation(
            "Main Menu (use arrow keys to select):",
            valid_options=["Run Confluence Downloader", "Parse/Search Logs", "Exit"],
            default="Run Confluence Downloader"
        )
        if main_choice == "Parse/Search Logs":
            print(f"{Fore.CYAN}\n=== Log Parsing Mode ==={Style.RESET_ALL}")
            default_log_file = 'confluence_downloader.log'
            log_file = input(f"{Fore.YELLOW}Enter path to log file [default: {default_log_file}]: {Style.RESET_ALL}").strip() or default_log_file
            filters = {'level': None, 'feature': None, 'api': None, 'keyword': None}
            while True:
                filter_choice = prompt_with_validation(
                    "Log Filter Options (use arrow keys to select):",
                    valid_options=[
                        "Log level" + (f" (current: {filters['level']})" if filters['level'] else ""),
                        "Feature tag" + (f" (current: {filters['feature']})" if filters['feature'] else ""),
                        "API call" + (f" (current: {filters['api']})" if filters['api'] else ""),
                        "Keyword" + (f" (current: {filters['keyword']})" if filters['keyword'] else ""),
                        "Run log search with current filters",
                        "Return to Main Menu"
                    ],
                    default="Run log search with current filters"
                )
                if filter_choice.startswith("Log level"):
                    filters['level'] = input(f"{Fore.YELLOW}Enter log level (INFO, WARNING, ERROR, etc.) or leave blank to clear: {Style.RESET_ALL}").strip() or None
                elif filter_choice.startswith("Feature tag"):
                    filters['feature'] = input(f"{Fore.YELLOW}Enter feature tag (e.g., LLM Combine, Download) or leave blank to clear: {Style.RESET_ALL}").strip() or None
                elif filter_choice.startswith("API call"):
                    filters['api'] = input(f"{Fore.YELLOW}Enter API call keyword (e.g., JIRA, Confluence) or leave blank to clear: {Style.RESET_ALL}").strip() or None
                elif filter_choice.startswith("Keyword"):
                    filters['keyword'] = input(f"{Fore.YELLOW}Enter keyword to search for or leave blank to clear: {Style.RESET_ALL}").strip() or None
                elif filter_choice == "Run log search with current filters":
                    print(f"{Fore.CYAN}\n=== Log Search Results (filters: {filters}) ==={Style.RESET_ALL}")
                    search_logs(log_file, level=filters['level'], feature=filters['feature'], api=filters['api'], keyword=filters['keyword'])
                    print(f"{Fore.CYAN}\n--- End of Results ---{Style.RESET_ALL}")
                elif filter_choice == "Return to Main Menu":
                    break
        elif main_choice == "Exit":
            print(f"{Fore.YELLOW}Exiting.{Style.RESET_ALL}")
            sys.exit(0)
        else:
            break
    # Continue with downloader as before
    args = get_args()
    if getattr(args, 'parse_logs', False):
        print(f"{Fore.CYAN}\n=== Log Parsing Mode ==={Style.RESET_ALL}")
        default_log_file = 'confluence_downloader.log'
        log_file = input(f"{Fore.YELLOW}Enter path to log file [default: {default_log_file}]: {Style.RESET_ALL}").strip() or default_log_file
        # Main log parsing submenu
        print(f"{Fore.CYAN}\n--- Log Filter Options ---{Style.RESET_ALL}")
        filters = {'level': None, 'feature': None, 'api': None, 'keyword': None}
        while True:
            print(f"{Fore.YELLOW}Select a filter to set or run the search:{Style.RESET_ALL}")
            print("  1. Log level" + (f" (current: {filters['level']})" if filters['level'] else ""))
            print("  2. Feature tag" + (f" (current: {filters['feature']})" if filters['feature'] else ""))
            print("  3. API call" + (f" (current: {filters['api']})" if filters['api'] else ""))
            print("  4. Keyword" + (f" (current: {filters['keyword']})" if filters['keyword'] else ""))
            print("  5. Run log search with current filters")
            print("  6. Exit log parser")
            choice = prompt_with_validation(
                f"{Fore.YELLOW}Enter 1, 2, 3, 4, 5, or 6:{Style.RESET_ALL}",
                valid_options=['1', '2', '3', '4', '5', '6'],
                default='5'
            )
            if choice == '1':
                filters['level'] = input(f"{Fore.YELLOW}Enter log level (INFO, WARNING, ERROR, etc.) or leave blank to clear: {Style.RESET_ALL}").strip() or None
            elif choice == '2':
                filters['feature'] = input(f"{Fore.YELLOW}Enter feature tag (e.g., LLM Combine, Download) or leave blank to clear: {Style.RESET_ALL}").strip() or None
            elif choice == '3':
                filters['api'] = input(f"{Fore.YELLOW}Enter API call keyword (e.g., JIRA, Confluence) or leave blank to clear: {Style.RESET_ALL}").strip() or None
            elif choice == '4':
                filters['keyword'] = input(f"{Fore.YELLOW}Enter keyword to search for or leave blank to clear: {Style.RESET_ALL}").strip() or None
            elif choice == '5':
                print(f"{Fore.CYAN}\n=== Log Search Results (filters: {filters}) ==={Style.RESET_ALL}")
                search_logs(log_file, level=filters['level'], feature=filters['feature'], api=filters['api'], keyword=filters['keyword'])
                print(f"{Fore.CYAN}\n--- End of Results ---{Style.RESET_ALL}")
            elif choice == '6':
                print(f"{Fore.YELLOW}Exiting log parser.{Style.RESET_ALL}")
                sys.exit(0)

    # Prompt for config file automation FIRST
    use_config = prompt_with_validation(
        f"{Fore.YELLOW}Run from config file? (y/n){Style.RESET_ALL}",
        valid_options=['y', 'n'],
        default='n'
    )
    if use_config == 'y':
        config_path = input(f"{Fore.YELLOW}Enter config file path [default: config.yaml]: {Style.RESET_ALL}").strip() or 'config.yaml'
        try:
            with open(config_path, 'r') as f:
                config_data = yaml.safe_load(f)
            if not config_data:
                print(f"{Fore.RED}Config file is empty or invalid!{Style.RESET_ALL}")
                sys.exit(1)
            # Fill in missing config values with defaults if not present in YAML
            defaults = {
                "base_url": DEFAULT_BASE_URL,
                "username": STUB_EMAIL,
                "mode": "2",
                "output_dir": DEFAULT_OUTPUT_DIR,
                "metrics_only": False,
                "parent_url": "",
                "space_key": "",
                "llm_combine": False,
                "llm_model": "gpt-3.5-turbo",
                "dry_run": False,
                "verbose": False,
                "llm_overwrite_mode": "overwrite",
                "llm_free_prompt_mode": "default",
            }
            # Update config_data with any missing defaults
            for key, value in defaults.items():
                if key not in config_data or config_data[key] is None:
                    config_data[key] = value
            # Detect multiple parent_url entries (parent_url, parent_url2, parent_url3, ...)
            parent_url_items = [(key, value) for key, value in config_data.items() if re.fullmatch(r"parent_url\d*", key) and value]
            parent_url_items.sort(key=lambda x: (int(x[0][10:]) if x[0] != "parent_url" else 0))
            parent_urls = [value for key, value in parent_url_items]
            # If more than one parent_url, run main for each
            if len(parent_urls) > 1:
                print(f"{Fore.CYAN}\n=== Multiple Parent Pages Detected in Config ==={Style.RESET_ALL}")
                for parent_index, parent_url_value in enumerate(parent_urls, 1):
                    print(f"{Fore.YELLOW}Processing parent page {parent_index}: {parent_url_value}{Style.RESET_ALL}")
                    config_data_copy = dict(config_data)
                    config_data_copy["parent_url"] = parent_url_value
                    from argparse import Namespace
                    args = Namespace(**config_data_copy)
                    # Bypass confirmation prompt for each parent page
                    result = main(args)
                    config_lines = [f"\nConfiguration for parent page {parent_index}:"]
                    for option_name, option_value in result['config'].items():
                        config_lines.append(f"  {option_name}: {option_value}")
                    # Add explicit reporting for both overwrite modes if not present
                    if 'overwrite_mode' in result['config']:
                        config_lines.append(f"  Overwrite Mode (File Downloads): {result['config'].get('overwrite_mode')}")
                    if 'llm_overwrite_mode' in config_data_copy:
                        config_lines.append(f"  Overwrite Mode (LLM Combine): {config_data_copy.get('llm_overwrite_mode')}")
                    config_lines.append(f"\nStatus: {result['status']}")
                    config_lines.append(result['message'])
                    print('\n'.join(config_lines))
                    if 'selected_options' in result:
                        selected_lines = [f"\n{Fore.CYAN}=== Selected Options ==={Style.RESET_ALL}"]
                        for option_name, option_value in result['selected_options'].items():
                            selected_lines.append(f"  {option_name}: {option_value}")
                        print('\n'.join(selected_lines))
                    if 'downloaded_files' in result:
                        if result['downloaded_files']:
                            files_section = [f"\n{Fore.CYAN}=== Downloaded Files ==={Style.RESET_ALL}"]
                            files_section += [f"  {file_path}" for file_path in result['downloaded_files']]
                            print('\n'.join(files_section))
                        else:
                            print(f"\n{Fore.CYAN}=== Downloaded Files ==={Style.RESET_ALL}\n  (No files were downloaded.)")
                    # LLM combine for each parent page
                    llm_combine = getattr(args, 'llm_combine', False)
                    llm_model = getattr(args, 'llm_model', None)
                    if llm_combine and result.get('downloaded_files'):
                        from llm_utils import combine_files_with_llm
                        openai_api_key = os.getenv('OPENAI_API_KEY')
                        if not openai_api_key:
                            print(f"{Fore.RED}OPENAI_API_KEY not set in environment. Skipping LLM combine step.{Style.RESET_ALL}")
                        else:
                            parent_title = None
                            # Try to get parent_title from result['config'] or result['message']
                            if 'config' in result and 'parent_url' in result['config']:
                                match = re.search(r'/pages/\d+/([^/]+)$', result['config']['parent_url'])
                                if match:
                                    parent_title = match.group(1).replace('+', '_').replace('-', '_')
                            # Fallback: use section/directory name from first downloaded file
                            if not parent_title and result.get('downloaded_files'):
                                first_file = result['downloaded_files'][0]
                                section_dir = os.path.basename(os.path.dirname(first_file))
                                parent_title = section_dir or f"ParentPage_{parent_index}"
                            # Use the directory containing the parent page's .md file for naming
                            parent_dir_part = None
                            if result.get('downloaded_files'):
                                output_dir = args.output_dir or 'confluence_pages'
                                # Find the most common subdirectory under 'Development' for this parent page's files
                                subdirs = []
                                for file_path in result['downloaded_files']:
                                    rel_path = os.path.relpath(file_path, output_dir)
                                    parts = rel_path.split(os.sep)
                                    if 'Development' in parts:
                                        dev_idx = parts.index('Development')
                                        if dev_idx + 1 < len(parts):
                                            subdirs.append(parts[dev_idx + 1])
                                            logging.debug(f"[LLM Naming] File: {file_path} | rel_path: {rel_path} | subdir after 'Development': {parts[dev_idx + 1]}")
                                    else:
                                        logging.debug(f"[LLM Naming] File: {file_path} | rel_path: {rel_path} | 'Development' not in path")
                                logging.info(f"[LLM Naming] Subdirectories found for parent page {parent_index}: {subdirs}")
                                # Use the most common subdir, or fallback to parent_title
                                if subdirs:
                                    from collections import Counter
                                    section, count = Counter(subdirs).most_common(1)[0]
                                    section_sanitized = re.sub(r'[^A-Za-z0-9]+', '_', section).strip('_')
                                    logging.info(f"[LLM Naming] Most common subdirectory for parent page {parent_index}: {section} (count: {count})")
                                    output_filename = f"LLM_Combined_{section_sanitized}.md"
                                else:
                                    logging.info(f"[LLM Naming] No subdirectory found for parent page {parent_index}, using parent_title: {parent_title}")
                                    output_filename = f"LLM_Combined_{parent_title}.md"
                                logging.info(f"[LLM Naming] Final output filename for parent page {parent_index}: {output_filename}")
                            logging.info(f"[LLM Naming] Files sent to LLM for parent page {parent_index}: {result['downloaded_files']}")
                            print(f"{Fore.YELLOW}Calling LLM to combine files for parent page {parent_index}... This may take a while.{Style.RESET_ALL}")
                            # Always set llm_overwrite_mode before using it
                            llm_overwrite_mode = config_data_copy.get('llm_overwrite_mode', 'overwrite')
                            logging.info(f"[LLM Combine] llm_overwrite_mode: {llm_overwrite_mode}")
                            logging.info(f"[LLM Combine] Intended output filename: {output_filename}")
                            llm_free_prompt_mode = config_data_copy.get('llm_free_prompt_mode', None)
                            paid_models = ["gpt-4", "gpt-4-turbo", "gpt-4-32k", "gpt-4o", "gpt-4-1106-preview"]
                            free_prompt_mode = llm_free_prompt_mode or "default"
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
                                free_prompt_mode = "quick" if prompt_choice == '2' else "default"
                            llm_output_path = combine_files_with_llm(
                                result['downloaded_files'],
                                args.output_dir or 'confluence_pages',
                                openai_api_key,
                                model=llm_model or 'gpt-3.5-turbo',
                                output_filename=output_filename,
                                overwrite_mode=llm_overwrite_mode,
                                free_prompt_mode=free_prompt_mode
                            )
                            logger = logging.getLogger("llm_combine")
                            if llm_output_path:
                                print(f"{Fore.GREEN}LLM-combined file saved to: {llm_output_path}{Style.RESET_ALL}")
                                logger.info(f"LLM-combined file saved to: {llm_output_path}")
                            else:
                                print(f"{Fore.RED}LLM combine failed. See logs for details.{Style.RESET_ALL}")
                                logger.error("LLM combine failed. No output file was created.")
                return  # End after all parent pages are processed
            # Otherwise, proceed as before with a single parent_url
            from argparse import Namespace
            args = Namespace(**config_data)
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
            # Add explicit reporting for both overwrite modes if not present
            if 'overwrite_mode' in result['config']:
                config_lines.append(f"  Overwrite Mode (File Downloads): {result['config'].get('overwrite_mode')}")
            if hasattr(args, 'llm_overwrite_mode'):
                config_lines.append(f"  Overwrite Mode (LLM Combine): {getattr(args, 'llm_overwrite_mode')}")
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
            # sys.exit(0)  # Remove this line to allow processing to continue after all parent pages
        except Exception as e:
            print(f"{Fore.RED}Failed to load config file: {e}{Style.RESET_ALL}")
            sys.exit(1)

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

    # Prompt for overwrite options for file downloads if not set
    if getattr(args, 'overwrite_mode', None) in (None, ''):
        print(f"{Fore.CYAN}\n=== Overwrite Options for File Downloads ===\n{Style.RESET_ALL}")
        overwrite_choice = prompt_with_validation(
            f"{Fore.YELLOW}{BATCH_PROMPT}\nEnter 1, 2, 3, or 4{Style.RESET_ALL}",
            valid_options=['1', '2', '3', '4'],
            default='1'
        )
        overwrite_map = {'1': 'overwrite', '2': 'skip', '3': 'ask', '4': 'increment'}
        args.overwrite_mode = overwrite_map[overwrite_choice]
    # Prompt for LLM combine overwrite mode if LLM combine is enabled and not set
    if getattr(args, 'llm_combine', False) and getattr(args, 'llm_overwrite_mode', None) in (None, ''):
        print(f"{Fore.CYAN}\n=== Overwrite Options for LLM Combined File ===\n{Style.RESET_ALL}")
        llm_overwrite_choice = prompt_with_validation(
            f"{Fore.YELLOW}How should the LLM combined file be saved if a file with the same name exists?\n  1. Overwrite the existing combined file\n  2. Increment the filename (e.g., LLM_Combined_XYZ_2.md)\nEnter 1 or 2 [default: 1]:{Style.RESET_ALL}",
            valid_options=['1', '2'],
            default='1'
        )
        llm_overwrite_map = {'1': 'overwrite', '2': 'increment'}
        args.llm_overwrite_mode = llm_overwrite_map[llm_overwrite_choice]
    # If still not set, default to 'overwrite'
    if getattr(args, 'llm_overwrite_mode', None) in (None, ''):
        args.llm_overwrite_mode = 'overwrite'

    # Print summary and confirm
    print(f"{Fore.CYAN}\n=== Summary of Selected Options ==={Style.RESET_ALL}")
    print(f"  Mode: {args.mode}")
    if args.mode == '2':
        print(f"  Parent URL: {args.parent_url}")
    print(f"  Dry Run: {args.dry_run}")
    print(f"  Overwrite Mode (File Downloads): {args.overwrite_mode}")
    print(f"  Overwrite Mode (LLM Combine): {args.llm_overwrite_mode}")
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
    # Add explicit reporting for both overwrite modes if not present
    if 'overwrite_mode' in result['config']:
        config_lines.append(f"  Overwrite Mode (File Downloads): {result['config'].get('overwrite_mode')}")
    if hasattr(args, 'llm_overwrite_mode'):
        config_lines.append(f"  Overwrite Mode (LLM Combine): {getattr(args, 'llm_overwrite_mode')}")
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
    parent_index = 1  # Ensure parent_index is defined for single-parent case
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
        llm_model_options = [
            ('1', 'gpt-3.5-turbo (free)'),
            ('2', 'gpt-4.1 (gpt-4-1106-preview, NOT free)'),
            ('3', 'gpt-4o (NOT free)'),
            ('4', 'claude-3.5-sonnet (NOT free, Anthropic API key required)')
        ]
        print(f"{Fore.YELLOW}Select LLM model for combining files:{Style.RESET_ALL}")
        for num, desc in llm_model_options:
            print(f"  {num}. {desc}")
        llm_model_choice = prompt_with_validation(
            f"{Fore.YELLOW}Enter 1, 2, 3, or 4 [default: 1]:{Style.RESET_ALL}",
            valid_options=['1', '2', '3', '4'],
            default='1'
        )
        llm_model_map = {
            '1': 'gpt-3.5-turbo',
            '2': 'gpt-4-1106-preview',
            '3': 'gpt-4o',
            '4': 'claude-3.5-sonnet'
        }
        llm_model = llm_model_map[llm_model_choice]
    if llm_combine:
        from llm_utils import combine_files_with_llm
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
            match = re.search(r'/pages/\d+/([^/]+)$', parent_url)
            if match:
                parent_name = match.group(1).replace('+', '_').replace('-', '_')
        if not parent_name:
            parent_name = 'ParentPage'
        # Use the directory containing the parent page's .md file for naming
        parent_dir_part = None
        if result.get('downloaded_files'):
            output_dir = args.output_dir or 'confluence_pages'
            # Find the most common subdirectory under 'Development' for this parent page's files
            subdirs = []
            for file_path in result['downloaded_files']:
                rel_path = os.path.relpath(file_path, output_dir)
                parts = rel_path.split(os.sep)
                if 'Development' in parts:
                    dev_idx = parts.index('Development')
                    if dev_idx + 1 < len(parts):
                        subdirs.append(parts[dev_idx + 1])
                        logging.debug(f"[LLM Naming] File: {file_path} | rel_path: {rel_path} | subdir after 'Development': {parts[dev_idx + 1]}")
                else:
                    logging.debug(f"[LLM Naming] File: {file_path} | rel_path: {rel_path} | 'Development' not in path")
            logging.info(f"[LLM Naming] Subdirectories found for parent page {parent_index}: {subdirs}")
            # Use the most common subdir, or fallback to parent_title
            if subdirs:
                from collections import Counter
                section, count = Counter(subdirs).most_common(1)[0]
                section_sanitized = re.sub(r'[^A-Za-z0-9]+', '_', section).strip('_')
                logging.info(f"[LLM Naming] Most common subdirectory for parent page {parent_index}: {section} (count: {count})")
                output_filename = f"LLM_Combined_{section_sanitized}.md"
            else:
                logging.info(f"[LLM Naming] No subdirectory found for parent page {parent_index}, using parent_title: {parent_name}")
                output_filename = f"LLM_Combined_{parent_name}.md"
            logging.info(f"[LLM Naming] Final output filename for parent page {parent_index}: {output_filename}")
        logging.info(f"[LLM Naming] Files sent to LLM for parent page {parent_index}: {result['downloaded_files']}")
        print(f"{Fore.YELLOW}Calling LLM to combine files... This may take a while.{Style.RESET_ALL}")
        logger.info(f"Calling OpenAI LLM with model: {llm_model or 'gpt-3.5-turbo'}")
        # Always set llm_overwrite_mode before using it
        llm_overwrite_mode = getattr(args, 'llm_overwrite_mode', 'overwrite')
        logging.info(f"[LLM Combine] llm_overwrite_mode: {llm_overwrite_mode}")
        logging.info(f"[LLM Combine] Intended output filename: {output_filename}")
        llm_free_prompt_mode = getattr(args, 'llm_free_prompt_mode', None)
        paid_models = ["gpt-4", "gpt-4-turbo", "gpt-4-32k", "gpt-4o", "gpt-4-1106-preview"]
        free_prompt_mode = llm_free_prompt_mode or "default"
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
            free_prompt_mode = "quick" if prompt_choice == '2' else "default"
        llm_output_path = combine_files_with_llm(
            result['downloaded_files'],
            args.output_dir or 'confluence_pages',
            os.getenv('OPENAI_API_KEY'),
            model=llm_model or 'gpt-3.5-turbo',
            output_filename=output_filename,
            overwrite_mode=llm_overwrite_mode,
            free_prompt_mode=free_prompt_mode
        )
        logger = logging.getLogger("llm_combine")
        if llm_output_path:
            print(f"{Fore.GREEN}LLM-combined file saved to: {llm_output_path}{Style.RESET_ALL}")
            logger.info(f"LLM-combined file saved to: {llm_output_path}")
        else:
            print(f"{Fore.RED}LLM combine failed. See logs for details.{Style.RESET_ALL}")
            logger.error("LLM combine failed. No output file was created.")

    # Prompt for all required options (if not set by YAML/CLI/env)
    prompt_mode(args) if not args.mode else None
    prompt_parent_url(args) if args.mode == '2' and not args.parent_url else None
    prompt_dry_run(args) if getattr(args, 'dry_run', None) is None else None
    # Advanced Options submenu
    from cli_helpers import prompt_advanced_options
    prompt_advanced_options(args)
    prompt_file_overwrite_mode(args) if getattr(args, 'overwrite_mode', None) in (None, '') else None

if __name__ == "__main__":
    run() 