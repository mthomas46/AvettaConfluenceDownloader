"""
file_ops.py
-----------
Handles all file and markdown operations for the Confluence Downloader project.
Includes filename sanitization, unique filename generation, and markdown consolidation logic.
No user interaction or printing occurs here (returns results for CLI to handle).
"""
import os
import re
from typing import List, Dict, Optional, Tuple
from bs4 import BeautifulSoup
from constants import DEFAULT_OUTPUT_DIR

def sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/*?":<>|]', '_', name)

def unique_filename(filename: str, output_dir: str, dir_path: str) -> str:
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

def consolidate_markdown_files(root_dir: str, output_filename: str = "Consolidated.md") -> Tuple[bool, str]:
    import glob
    consolidated = []
    seen_lines = set()
    for path in glob.glob(os.path.join(root_dir, "**", "*.md"), recursive=True):
        fname = os.path.basename(path).lower()
        if fname in {"metrics.md", output_filename.lower()}: continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            consolidated.append(f"\n---\n\n# {os.path.splitext(os.path.basename(path))[0].replace('_',' ').replace('-',' ')}\n\n")
            for line in lines:
                if line.strip() and line not in seen_lines:
                    consolidated.append(line)
                    seen_lines.add(line)
        except Exception as e:
            return False, f"Error reading {path}: {e}"
    out_path = os.path.join(root_dir, output_filename)
    try:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("""# Consolidated Developer Documentation\n\nThis document combines all unique information from Markdown files in this directory.\n\n""")
            f.writelines(consolidated)
        return True, out_path
    except Exception as e:
        return False, f"Error writing consolidated file: {e}"

def confluence_storage_to_markdown(storage_html: str) -> str:
    """
    Convert Confluence storage format (XHTML) to Markdown.
    """
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