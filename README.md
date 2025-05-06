# Avetta Confluence Downloader

> **A modern CLI tool to download, archive, and consolidate Confluence pages as Markdown, with advanced LLM-powered file combination.**
> 
> **IMPORTANT:** This script is tested and supported only on **Python 3.11** and **3.12**. Some dependencies (such as `lxml`) may not work on Python 3.13+ or older versions. Please use Python 3.12 or 3.11 for best compatibility.

---

## Table of Contents
- [Overview](#overview)
- [Key Features](#key-features)
- [Python Version Compatibility](#python-version-compatibility)
- [Project Structure](#project-structure)
- [Configuration & Usage](#configuration--usage)
  - [Configuration (.env)](#configuration-env)
  - [Batch YAML Configuration (Multi-Parent Page Download)](#batch-yaml-configuration-multi-parent-page-download)
  - [CLI Options](#cli-options)
  - [Quick Start](#quick-start)
  - [Example Workflows](#example-workflows)
- [Output](#output)
- [LLM Combine Feature](#llm-combine-feature)
- [Logging Strategies](#logging-strategies)
- [API Usage](#api-usage)
- [Development & Contribution](#development--contribution)
- [Troubleshooting](#troubleshooting)
- [License](#license)

---

## Overview

**Avetta Confluence Downloader** is a CLI tool for downloading Confluence pages as Markdown files, preserving hierarchy, and generating metrics reports. It supports both command-line and interactive usage, making it ideal for archiving, documentation, or analysis of Confluence content. Advanced features include batch downloads and LLM-powered file consolidation.

## Key Features

- **Modern, Colorful CLI:** User prompts are colorized and clearly separated for a better terminal experience.
- **Interactive Flow:** The script guides you through all required options, shows a summary, and asks for confirmation before running.
- **Flexible Configuration:** Supports `.env`, command-line arguments, YAML config, and interactive prompts.
- **Batch Download:** Download multiple parent pages in one run using YAML config.
- **Dry Run Mode:** Preview all actions (including overwrite logic) without writing any files.
- **Overwrite Options:** Choose to overwrite, skip, increment, or decide for each file interactively.
- **API Token Security:** API token is masked in all output/logs, and a warning is shown if passed as a CLI argument.
- **Graceful Interrupts:** Cleanly handles `Ctrl+C` (KeyboardInterrupt).
- **Concurrent Downloads:** Fast downloads with a thread pool (default: 10 threads).

## Python Version Compatibility

- **Supported:** Python 3.11 and 3.12 only.
- **Why:** Some dependencies (notably `lxml`) may not install or work on Python 3.13+ or older versions.
- **How to check:**
  ```sh
  python --version
  # or
  python3 --version
  ```
- **How to install Python 3.12:** See [Troubleshooting](#troubleshooting) for `pyenv` instructions.

## Project Structure

```
AvettaConfluenceDownloader/
├── cli.py                # Handles all user interaction, argument parsing, and CLI entry point
├── main.py               # Orchestrates the main workflow, delegates logic to modules
├── config.py             # Handles environment/config loading and validation
├── confluence_api.py     # All Confluence API interaction functions
├── file_ops.py           # File/markdown operations, saving, and consolidation
├── constants.py          # Default values, stub values, and user-facing messages
├── requirements.txt      # Python dependencies (pinned versions)
├── README.md             # Project documentation
├── .gitignore            # Git ignore rules
├── .env.example          # Example environment config
├── confluence_downloader.log  # Log file (created at runtime)
├── .venv/                # (Optional) Virtual environment
├── tests/                # (Recommended) Unit tests for the codebase
└── ...                   # Output directories/files
```

---

## Configuration & Usage

This section covers how to configure and use the downloader, including environment variables, YAML batch config, CLI options, and example workflows.

### Configuration (.env)
- Copy `.env.example` to `.env` and fill in your Confluence base URL, username, API token, and output directory.
- Environment variables:
  - `CONFLUENCE_BASE_URL`: Confluence base URL
  - `CONFLUENCE_USERNAME`: Confluence username/email
  - `CONFLUENCE_API_TOKEN`: Confluence API token
  - `OUTPUT_DIR`: Output directory for downloaded files
  - `OPENAI_API_KEY`: OpenAI API key (required for LLM combine)
  - `ANTHROPIC_API_KEY`: Anthropic API key (required for Claude models)
- Environment variables can be overridden by CLI arguments or YAML config.

### Batch YAML Configuration (Multi-Parent Page Download)

You can specify multiple parent pages in your `config.yaml` for batch processing. Use keys like `parent_url`, `parent_url2`, `parent_url3`, etc. The downloader will process each parent page in sequence, generating separate outputs for each.

Example `config.yaml`:

```yaml
base_url: "https://your-domain.atlassian.net/wiki"
username: "your.email@example.com"
mode: "2"
output_dir: "./confluence_pages"
parent_url: "https://your-domain.atlassian.net/wiki/spaces/IT/pages/123456789/Workstation+Setup"
parent_url2: "https://your-domain.atlassian.net/wiki/spaces/IT/pages/987654321/UI+Development"
parent_url3: "https://your-domain.atlassian.net/wiki/spaces/IT/pages/192837465/BE+Development"
llm_combine: true
llm_model: "gpt-3.5-turbo"
llm_overwrite_mode: "overwrite"  # or "increment" to avoid overwriting combined files
llm_free_prompt_mode: "default"  # or "quick" for a shorter prompt (free models only)
metrics_only: false
space_key: "IT"
dry_run: false
verbose: false
```

Each parent page will be downloaded and, if `llm_combine` is enabled, a uniquely named combined file will be generated for each (e.g., `LLM_Combined_Workstation_Setup.md`).

### CLI Options

| Option                | Description                                              | Example/Values                        |
|-----------------------|----------------------------------------------------------|---------------------------------------|
| --base-url            | Confluence base URL                                      | https://your-domain.atlassian.net/wiki|
| --username            | Confluence username/email                                | your.email@example.com                |
| --mode                | Download mode                                            | 1 (entire space), 2 (by parent page)  |
| --output-dir          | Output directory for downloaded files                    | ./confluence_pages                    |
| --metrics-only        | Only generate metrics report (no page downloads)         | (flag)                                |
| --parent-url          | Parent page URL (for mode 2)                             | https://.../pages/123456789/...       |
| --space-key           | Space key (for mode 1)                                   | DEV                                   |
| --dry-run             | Preview actions without writing files                    | (flag)                                |
| --version             | Show script version and exit                             | (flag)                                |
| --verbose             | Enable verbose (DEBUG) logging                           | (flag)                                |
| --llm-combine         | Combine downloaded files using an LLM and save the result| (flag)                                |
| --llm-model           | OpenAI/Anthropic LLM model to use for combining files    | gpt-3.5-turbo (default, free), gpt-4-1106-preview, gpt-4o, claude-3.5-sonnet |
| --llm-overwrite-mode  | LLM combine file overwrite mode: overwrite (default) or increment (add number if file exists) | overwrite, increment |
| --llm-free-prompt-mode| Free LLM prompt style: default (detailed) or quick (short)| default, quick                        |

- Any option not provided will be prompted for interactively, with colorized and clear prompts.
- After all options are collected, a summary is shown and you must confirm before the script runs.

### Quick Start

1. Copy `.env.example` to `.env` and fill in your credentials and API keys.
2. Optionally, create a `config.yaml` for batch or automated runs.
3. Run the script and follow the prompts, or use CLI options for automation.

### Example Workflows

- **Download all pages under a parent page (interactive):**
  ```sh
  python cli.py
  ```
  (Follow the prompts for mode, parent URL, dry run, and overwrite options.)

- **Download all pages under a parent page (non-interactive):**
  ```sh
  python cli.py --mode 2 --parent-url "https://your-domain.atlassian.net/wiki/spaces/IT/pages/123456789/Parent+Page" --output-dir ./confluence_pages
  ```

- **Dry run (simulate, no files written):**
  ```sh
  python cli.py --dry-run
  ```

- **Verbose logging:**
  ```sh
  python cli.py --verbose
  ```

- **Show version:**
  ```sh
  python cli.py --version
  ```

- **Combine downloaded files with LLM (interactive):**
  ```sh
  python cli.py --llm-combine
  ```
  (Follow the prompts for mode, parent URL, dry run, overwrite options, and LLM model.)

- **Combine downloaded files with LLM (non-interactive):**
  ```sh
  python cli.py --mode 2 --parent-url "https://your-domain.atlassian.net/wiki/spaces/IT/pages/123456789/Parent+Page" --llm-combine
  ```
  (The combined file will be named after the parent page, e.g., `Parent_Page_combined.md`.)

---

## Output

The script saves downloaded pages as Markdown files in the specified output directory, preserving the Confluence page hierarchy. A metrics report (`metrics.md`) is generated summarizing the download (page count, metadata, etc.). Optionally, you can consolidate all markdown files into a single document (`Consolidated.md`). Logs are written to `confluence_downloader.log` for troubleshooting and auditing. Progress is shown with modern progress bars (tqdm) and spinners for all major steps, so you always know the script is working. Dry run mode prints all actions that would be taken, including overwrite logic, without writing any files. At the end of the run, the CLI displays a summary of selected options and a list of all files that were downloaded (or would be downloaded in dry run mode).

---

## LLM Combine Feature

> **Context:** The LLM Combine feature lets you merge all downloaded Markdown files for a parent page into a single, improved document using a Large Language Model (LLM) such as OpenAI's GPT or Anthropic's Claude. This is especially useful for creating a unified, readable knowledge base from multiple Confluence pages.

**How to use:**
- Use the `--llm-combine` flag, or answer "yes" to the interactive prompt after download.
- You can also set `llm_combine: true` in your `config.yaml` for batch or automated runs.
- Control file overwrite behavior with `--llm-overwrite-mode` (CLI) or `llm_overwrite_mode` (YAML):
  - `overwrite` (default): Overwrite the combined file if it exists.
  - `increment`: If the combined file exists, create a new file with a numeric suffix (e.g., `LLM_Combined_2.md`).
- The script will use your OpenAI API key (set `OPENAI_API_KEY` in your `.env` or environment) or Anthropic API key (for Claude).
- You can select the model with `--llm-model` or interactively. **Only `gpt-3.5-turbo` is free.**
- **Available models:**
  - `gpt-3.5-turbo` (free, OpenAI)
  - `gpt-4-1106-preview` (**NOT free**, OpenAI paid account required)
  - `gpt-4o` (**NOT free**, OpenAI paid account required)
  - `claude-3.5-sonnet` (**NOT free**, Anthropic API key required)
- The output file will be named after the parent page or section (e.g., `LLM_Combined_Workstation_Setup.md`).
- The script will print the path to the combined file after completion.
- **Prompt selection:**
  - For paid models, a detailed technical writing prompt is used.
  - For free models, you can choose between:
    - **Default:** A detailed, organized prompt with AI note and formatting guide.
    - **Quick:** A short, direct prompt: `combine these files into 1. preserve all unique information. improve readability and flow. create sections and reorder information based on need and where applicable`.
  - The prompt type and a preview are logged for each LLM combine run.

**What happens under the hood:**
When combining files, the script instructs the LLM to:
- **Deduplicate:** Remove any duplicate information across the input files.
- **Section:** Organize the content into logical sections, grouping related topics together.
- **Reorder:** Rearrange content to improve the flow and ensure related information is presented together.
- **Improve Readability:** Rewrite and restructure content for clarity and ease of reading.
- **Preserve Unique Information:** Ensure all unique details from the original files are retained in the final output.

These strategies help produce a single, comprehensive, and well-organized Markdown document from multiple Confluence pages.

**LLM Prompt Used (examples):**
- **Default (free):**
  > You are a technical writer. Combine the content of all these files into a single, well-structured Markdown document. ...
- **Quick (free):**
  > combine these files into 1. preserve all unique information. improve readability and flow. create sections and reorder information based on need and where applicable
- **Paid:**
  > You are acting as a professional technical writer. Your goal is to create a single, comprehensive, and easy-to-navigate Markdown document ...

**Modular usage:**
You can use the `llm_utils.combine_files_with_llm` function directly in your own scripts for automation:
```python
from llm_utils import combine_files_with_llm
combined_path = combine_files_with_llm([
    'file1.md', 'file2.md', ...
], output_dir='.', api_key='sk-...', model='gpt-3.5-turbo', output_filename='Combined.md', overwrite_mode='overwrite', free_prompt_mode='default')
```

**Warning:** Only `gpt-3.5-turbo` is free. All other models require a paid OpenAI or Anthropic account and the correct API key. You will be warned in the CLI if you select a non-free model.

---

## Multi-Parent Batch Support

- You can specify multiple parent pages in your YAML config using `parent_url`, `parent_url2`, etc.
- The script will process each parent page in sequence, generating separate outputs for each.
- All LLM combine and file naming logic is applied per parent page.

---

## Logging

- All major steps, errors, and configuration choices are logged to `confluence_downloader.log`.
- The LLM combine step logs the prompt type and a preview of the prompt used for each run.
- Overwrite/increment logic and output filenames are logged for traceability.

---

## Logging Strategies

The downloader uses Python's `logging` module to provide detailed information about its operation. Logging levels can be controlled with the `--verbose` flag or by configuring the logger in your own scripts.

### Key Logging Features:
- **Download Progress:** Logs each page being saved, converted, or if any errors occur.
- **Batch Processing:** Logs which parent page is being processed in batch mode.
- **LLM Combine Naming:**
  - Logs each file considered for LLM combination, its relative path, and the subdirectory after `Development`.
  - Logs the list of subdirectories found for each parent page.
  - Logs the most common subdirectory and the final output filename chosen for the LLM-combined file.
  - If no subdirectory is found, logs fallback to the parent page title.
- **API Requests:** Logs HTTP requests to the LLM API and their responses.

**Tip:** For the most detailed output, set the logging level to `DEBUG`.

---

## API Usage

This script interacts with the [Confluence Cloud REST API](https://developer.atlassian.com/cloud/confluence/rest/intro/):

- **Authentication:**
  - Uses HTTP Basic Auth with your Confluence username/email and an [API token](https://id.atlassian.com/manage-profile/security/api-tokens).
  - Your credentials are never stored; they are only used for the session.
- **Endpoints Used:**
  - `GET /rest/api/content` — List all pages in a space.
  - `GET /rest/api/content/{id}/descendant/page` — List all descendant pages under a parent page.
  - `GET /rest/api/content/search` — Search for pages by title.
  - `GET /rest/api/content/{id}` — Fetch a single page's details.
- **Data Handling:**
  - Page content is retrieved in Confluence storage format (XHTML) and converted to Markdown.
  - Ancestor information is used to preserve the page hierarchy in the output directory.
  - A metrics report is generated with page metadata (created, updated, viewed, etc.).

---

## Development & Contribution

- **Issues & PRs:** Please use GitHub Issues for bugs/feature requests and submit Pull Requests for improvements.
- **Code Style:** Follow [PEP8](https://peps.python.org/pep-0008/) for Python code. Use meaningful commit messages. The codebase is compatible with [black](https://black.readthedocs.io/) and [flake8](https://flake8.pycqa.org/).
- **Readability:** The codebase uses descriptive variable names (no single-letter placeholders), clear function-level docstrings, and inline comments to maximize human readability and maintainability.
- **Type Hints:** Functions should use Python type hints for clarity and editor support.
- **Testing:**
  - To add tests, create a `tests/` directory and use [pytest](https://docs.pytest.org/).
  - Example test (in `tests/test_args.py`):
    ```python
    from confluence_downloader import get_args
    def test_args():
        assert get_args() is not None
    ```
  - To run tests:
    ```sh
    pip install pytest
    pytest
    ```
- **Dependencies:** Add new dependencies to `requirements.txt` and pin versions.
- **Sensitive Data:** Never commit API tokens, credentials, or output files containing sensitive information.

---

## Troubleshooting

- If you encounter permission errors, ensure your user has access to the requested pages/spaces.
- For large spaces, be patient—downloads may take a while.
- Check `confluence_downloader.log` for detailed logs and error messages.
- If you see errors about short links (e.g., `/x/ABC123`), open the link in your browser and use the redirected full URL.

### Common Issues and Solutions

**1. lxml or parser errors:**
- **Error:** `Couldn't find a tree builder with the features you requested: lxml. Do you need to install a parser library?`
- **Solution:**
  - Make sure you have installed all requirements:
    ```sh
    pip install -r requirements.txt
    ```
  - If you see build errors for `lxml`, ensure you are using Python 3.12 or 3.11 (not 3.13+), as some C extensions may not yet support the latest Python versions.
  - If you are on macOS and see build errors, you may need to run:
    ```sh
    brew install libxml2 libxslt
    export LDFLAGS="-L/opt/homebrew/opt/libxml2/lib -L/opt/homebrew/opt/libxslt/lib"
    export CPPFLAGS="-I/opt/homebrew/opt/libxml2/include -I/opt/homebrew/opt/libxslt/include"
    pip install lxml
    ```

**2. Python version compatibility:**
- **Error:** `pip install lxml` fails or requirements fail to install on Python 3.13+
- **Solution:**
  - Use Python 3.12 or 3.11 for this project. You can manage multiple Python versions with [pyenv](https://github.com/pyenv/pyenv):
    ```sh
    pyenv install 3.12.3
    pyenv local 3.12.3
    python -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    ```

**3. Virtual environment not activated:**
- **Error:** `ModuleNotFoundError` for any required package.
- **Solution:**
  - Make sure you have activated your virtual environment:
    ```