"""
confluence_api.py
-----------------
Handles all Confluence API interactions for the Confluence Downloader project.
Includes page search, retrieval, and ID extraction logic.
No user interaction or printing occurs here (returns results for CLI to handle).
"""
import requests
import re
from typing import List, Dict, Optional, Tuple
from colorama import Fore, Style
import logging

def search_pages_by_title(base_url: str, auth: Tuple[str, str], search_term: str) -> List[Dict]:
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

def get_space_key_from_url(url: str) -> Optional[str]:
    match = re.search(r'/spaces/([^/]+)', url)
    return match.group(1) if match else None

def get_page_id_from_url(url: str, base_url: Optional[str] = None, auth: Optional[Tuple[str, str]] = None) -> Optional[str]:
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

def get_all_pages_in_space(base_url: str, auth: Tuple[str, str], space_key: str) -> List[Dict]:
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

def get_descendants(base_url: str, auth: Tuple[str, str], page_id: str) -> List[Dict]:
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