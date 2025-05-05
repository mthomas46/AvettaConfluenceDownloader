# Avetta Confluence Downloader

> **IMPORTANT:** This script is tested and supported only on **Python 3.11** and **3.12**. Some dependencies (such as `lxml`) may not work on Python 3.13+ or older versions. Please use Python 3.12 or 3.11 for best compatibility.

---

## Table of Contents
- [Overview](#overview)
- [Key Features](#key-features)
- [Python Version Compatibility](#python-version-compatibility)
- [Project Structure](#project-structure)
- [Quick Start](#quick-start)
- [Using pyenv to Manage Python Versions](#using-pyenv-to-manage-python-versions)
- [Configuration (.env)](#configuration-env)
- [Usage](#usage)
  - [Running from the Terminal](#running-from-the-terminal)
  - [Running from an IDE](#running-from-an-ide-eg-pycharm-vscode)
- [Output](#output)
- [Example Workflows](#example-workflows)
- [API Usage](#api-usage)
- [Development & Contribution](#development--contribution)
- [Troubleshooting](#troubleshooting)
- [License](#license)

---

## Overview

**Avetta Confluence Downloader** downloads Confluence pages as Markdown files and generates a metrics report. It supports both command-line and interactive usage, making it ideal for archiving, documentation, or analysis of Confluence content.

## Key Features
- **Modern Progress Bar:** Uses [tqdm](https://tqdm.github.io/) for a robust progress bar.
- **Flexible Configuration:** Supports `.env`, command-line arguments, and interactive prompts.
- **API Token Security:** API token is masked in all output/logs, and a warning is shown if passed as a CLI argument.
- **Graceful Interrupts:** Cleanly handles `Ctrl+C` (KeyboardInterrupt).
- **Concurrent Downloads:** Fast downloads with a thread pool (default: 10 threads).
- **Pinned Dependencies:** All dependencies are version-pinned for reproducibility.

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
├── confluence_downloader.py   # Main script
├── requirements.txt           # Python dependencies (pinned versions)
├── README.md                  # Project documentation
├── .gitignore                 # Git ignore rules
├── .env.example               # Example environment config
├── confluence_downloader.log  # Log file (created at runtime)
├── .venv/                     # (Optional) Virtual environment
└── ...                        # Output directories/files
```

---

## Quick Start

1. **Install Python 3.12 or 3.11** (see [Python Version Compatibility](#python-version-compatibility)).
   - If you need to manage multiple Python versions, see [Using pyenv to Manage Python Versions](#using-pyenv-to-manage-python-versions).
2. **Create and activate a virtual environment:**
   ```sh
   python3.12 -m venv .venv
   source .venv/bin/activate
   ```
3. **Install dependencies:**
   ```sh
   pip install -r requirements.txt
   ```
4. **Copy and edit the environment file:**
   ```sh
   cp .env.example .env
   # Edit .env with your Confluence base URL, username, API token, and output directory
   ```
5. **Run the script:**
   ```sh
   python confluence_downloader.py
   ```

---

## Using pyenv to Manage Python Versions

If your system Python is not 3.12 or 3.11, or you want to manage multiple Python versions, use [pyenv](https://github.com/pyenv/pyenv):

**Install pyenv:**
- On macOS:
  ```sh
  brew install pyenv
  ```
- On Ubuntu/Debian:
  ```sh
  curl https://pyenv.run | bash
  # Follow the printed instructions to add pyenv to your shell profile
  ```

**Install Python 3.12:**
```sh
pyenv install 3.12.3
```

**Set Python 3.12 for your project directory:**
```sh
pyenv local 3.12.3
```
This creates a `.python-version` file in your project folder.

**Create and activate a virtual environment:**
```sh
python -m venv .venv
source .venv/bin/activate
```

**Install requirements and run the script as usual.**

---

## Configuration (.env)

- Use the provided `.env.example` as a template.
- Fill in:
  - `CONFLUENCE_BASE_URL` (e.g., `https://your-domain.atlassian.net/wiki`)
  - `CONFLUENCE_USERNAME` (your email/username)
  - `CONFLUENCE_API_TOKEN` (your API token)
  - `OUTPUT_DIR` (output directory, e.g., `confluence_pages`)
- The script loads values from `.env` automatically. Any missing or stub value will be prompted for interactively.
- **Never commit your real `.env` file to version control!**

---

## Usage

### Running from the Terminal

- **Interactive mode:**
  ```sh
  python confluence_downloader.py
  ```
- **With command-line arguments:**
  ```sh
  python confluence_downloader.py --base-url https://your-domain.atlassian.net/wiki \
      --username your.email@example.com \
      --mode 1 \
      --space-key DEV \
      --output-dir ./confluence_pages
  ```
- **Dry run (simulate, no files written):**
  ```sh
  python confluence_downloader.py --dry-run
  ```
- **Verbose logging:**
  ```sh
  python confluence_downloader.py --verbose
  ```
- **Show version:**
  ```sh
  python confluence_downloader.py --version
  ```

**Tip:** You can mix command-line arguments, `.env`, and interactive prompts. Any argument not provided will be loaded from `.env` or prompted for interactively.

#### Available Arguments
- `--base-url`         : Confluence base URL
- `--username`         : Confluence username/email
- `--mode`             : 1 (entire space), 2 (by parent page), or 3 (search by title)
- `--output-dir`       : Output directory for downloaded files
- `--metrics-only`     : Only generate a metrics report (no page downloads)
- `--parent-url`       : Parent page URL (for mode 2)
- `--space-key`        : Space key (for mode 1)
- `--dry-run`          : Preview actions without writing files
- `--version`          : Show script version and exit
- `--verbose`          : Enable verbose (DEBUG) logging

### Running from an IDE (e.g., PyCharm, VSCode)

1. Open the project folder in your IDE.
2. Open `confluence_downloader.py`.
3. Click the Run/Debug button, or right-click the file and select "Run".
4. To pass arguments, configure the run configuration (usually via a menu or toolbar in your IDE).

---

## Output
- Downloaded pages are saved as text/markdown files in the specified output directory, preserving the Confluence page hierarchy.
- A metrics report (`metrics.md`) is generated summarizing the download (page count, metadata, etc.).
- Optionally, you can consolidate all markdown files into a single document (`Consolidated.md`).
- Logs are written to `confluence_downloader.log` for troubleshooting and auditing.
- Progress is shown with a modern progress bar (tqdm).

---

## Example Workflows

- **Download all pages in a space:**
  ```sh
  python confluence_downloader.py --mode 1 --space-key DEV
  ```
- **Download all pages under a parent page:**
  ```sh
  python confluence_downloader.py --mode 2 --parent-url "https://your-domain.atlassian.net/wiki/spaces/IT/pages/123456789/Parent+Page"
  ```
- **Search and download by page title:**
  ```sh
  python confluence_downloader.py --mode 3
  # Then follow the interactive prompts to select pages
  ```

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
    ```sh
    source .venv/bin/activate
    ```

**4. Still having issues?**
- Paste the error message into an issue or support request for help.
- Check the `confluence_downloader.log` file for more details.

---

## License

This project is licensed under the MIT License. 