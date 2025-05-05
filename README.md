# Avetta Confluence Downloader

## Overview

This tool downloads Confluence pages as Markdown files and generates a metrics report. It supports both command-line and interactive usage, and is suitable for archiving, documentation, or analysis of Confluence content.

## Project Structure

```
AvettaConfluenceDownloader/
├── confluence_downloader.py   # Main script
├── requirements.txt           # Python dependencies
├── README.md                  # Project documentation
├── .gitignore                 # Git ignore rules
├── confluence_downloader.log  # Log file (created at runtime)
├── .venv/                     # (Optional) Virtual environment
└── ...                        # Output directories/files
```

- All code is in `confluence_downloader.py` for now.
- Output and logs are not tracked by git (see `.gitignore`).

## Development & Contribution

- **Issues & PRs:** Please use GitHub Issues for bugs/feature requests and submit Pull Requests for improvements.
- **Code Style:** Follow [PEP8](https://peps.python.org/pep-0008/) for Python code. Use meaningful commit messages.
- **Testing:** If you add new features, please include basic tests or usage examples in the PR/README.
- **Dependencies:** Add new dependencies to `requirements.txt`.
- **Sensitive Data:** Never commit API tokens, credentials, or output files containing sensitive information.

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

## Setup

1. (Recommended) Create and activate a virtual environment:
   ```sh
   python3 -m venv .venv
   source .venv/bin/activate
   ```
2. Install dependencies:
   ```sh
   pip install -r requirements.txt
   ```

## Running from the Terminal

You can run the script in two ways:

### 1. With Command-Line Arguments

This is useful for automation or when you want to skip interactive prompts. Example:

```sh
python3 confluence_downloader.py --base-url https://your-domain.atlassian.net/wiki \
    --username your.email@example.com \
    --mode 1 \
    --space-key DEV \
    --output-dir ./confluence_pages
```

**Available arguments:**
- `--base-url`         : Confluence base URL (e.g., https://your-domain.atlassian.net/wiki)
- `--username`         : Confluence username/email
- `--mode`             : 1 (entire space), 2 (by parent page), or 3 (search by title)
- `--output-dir`       : Output directory for downloaded files
- `--metrics-only`     : Only generate a metrics report (no page downloads)
- `--parent-url`       : Parent page URL (for mode 2)
- `--space-key`        : Space key (for mode 1)
- `--dry-run`          : Preview actions without writing files

See all options:
```sh
python3 confluence_downloader.py --help
```

### 2. Interactive Mode

If you run the script without arguments, it will prompt you for all required information:

```sh
python3 confluence_downloader.py
```

You will be asked for:
- Confluence base URL
- Username/email
- API token (input hidden)
- Download mode (entire space, by parent page, or search by title)
- Output directory
- Whether to generate only metrics or also download pages
- Confirmation for large downloads
- (Optional) Consolidation of markdown files after download

**Tip:** You can mix command-line arguments and interactive prompts. Any argument not provided will be prompted for interactively.

## Running from an IDE (e.g., PyCharm, VSCode)

1. Open the project folder in your IDE.
2. Open `confluence_downloader.py`.
3. Click the Run/Debug button, or right-click the file and select "Run".
4. To pass arguments, configure the run configuration (usually via a menu or toolbar in your IDE).

## Output
- Downloaded pages are saved as text/markdown files in the specified output directory, preserving the Confluence page hierarchy.
- A metrics report (`metrics.md`) is generated summarizing the download (page count, metadata, etc.).
- Optionally, you can consolidate all markdown files into a single document (`Consolidated.md`).
- Logs are written to `confluence_downloader.log` for troubleshooting and auditing.

## Example Workflows

- **Download all pages in a space:**
  ```sh
  python3 confluence_downloader.py --mode 1 --space-key DEV
  ```
- **Download all pages under a parent page:**
  ```sh
  python3 confluence_downloader.py --mode 2 --parent-url "https://your-domain.atlassian.net/wiki/spaces/IT/pages/123456789/Parent+Page"
  ```
- **Search and download by page title:**
  ```sh
  python3 confluence_downloader.py --mode 3
  # Then follow the interactive prompts to select pages
  ```

## Authentication
- You will need a Confluence API token. [Get your API token here.](https://id.atlassian.com/manage-profile/security/api-tokens)
- Your API token is used only for the session and not stored.

## Troubleshooting
- If you encounter permission errors, ensure your user has access to the requested pages/spaces.
- For large spaces, be patient—downloads may take a while.
- Check `confluence_downloader.log` for detailed logs and error messages.
- If you see errors about short links (e.g., `/x/ABC123`), open the link in your browser and use the redirected full URL.

## Contributing

Contributions are welcome! Please open issues or submit pull requests for improvements, bug fixes, or new features.

## License

This project is licensed under the MIT License. 