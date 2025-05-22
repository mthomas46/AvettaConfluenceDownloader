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
import json
import os
import time
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
import glob
from collections import defaultdict

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

def get_all_spaces(base_url: str, auth: tuple) -> list:
    """Fetch all Confluence spaces (returns list of dicts with key and name), always using cache if available."""
    cache_dir = "cache"
    os.makedirs(cache_dir, exist_ok=True)
    cache_path = os.path.join(cache_dir, "spaces.json")
    # Always use cache if available
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cache = json.load(f)
            return cache.get("spaces", [])
        except Exception:
            pass
    # Fetch from API if cache is missing or unreadable
    spaces = []
    start, limit = 0, 50
    while True:
        params = {'limit': limit, 'start': start}
        try:
            r = requests.get(f"{base_url}/rest/api/space", params=params, auth=auth)
            r.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"{Fore.RED}Error fetching spaces: {e}{Style.RESET_ALL}")
            break
        data = r.json()
        spaces.extend(data.get('results', []))
        if data.get('_links', {}).get('next'):
            start += limit
        else:
            break
    # Save to cache
    try:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump({"spaces": [{'key': s['key'], 'name': s.get('name', s['key'])} for s in spaces]}, f)
    except Exception:
        pass
    return [{'key': s['key'], 'name': s.get('name', s['key'])} for s in spaces]

def summarize_confluence_document(doc_source, base_url=None, auth=None, llm_call=None):
    """
    Summarize a Confluence document using an LLM prompt, from either a URL or a cached/downloaded file.
    - doc_source: URL (str) or file path (str)
    - base_url, auth: required if fetching from URL
    - llm_call: function that takes a prompt string and returns the LLM's response
    Returns: summary string
    """
    # Prompt template
    prompt = '''You are an expert technical writer and information architect.
Read the following Confluence document. Your goal is to produce a concise, information-rich summary that captures all key points, structure, and unique content, while omitting boilerplate, navigation, or irrelevant details.

Guidelines:
- Focus on the main topics, decisions, processes, and any unique or actionable information.
- Preserve the logical structure (sections, bullet points, tables) in a condensed form.
- Include important definitions, instructions, or data, but do not copy large blocks of text verbatim.
- Omit page headers/footers, navigation, and unrelated links.
- If the document contains code, configs, or examples, summarize their purpose and include only the most essential snippets.
- If there are action items, decisions, or owners, include them.
- The summary should be clear and self-contained, so it can be used as context for future LLM queries about this document or related topics.

Output Format:
- Use Markdown.
- Start with a one-sentence summary of the document's purpose.
- Then provide a structured outline or bullet points of the main content.
- If relevant, include a "Key Takeaways" or "Action Items" section at the end.

---

Document to Summarize:
```
{content}
```
'''
    # Fetch content
    if doc_source.startswith('http://') or doc_source.startswith('https://'):
        if not (base_url and auth):
            raise ValueError("base_url and auth required for URL fetch")
        # Extract page ID from URL
        import re
        match = re.search(r'pageId=(\d+)', doc_source)
        if not match:
            raise ValueError("Could not extract pageId from URL")
        page_id = match.group(1)
        # Fetch page content via API
        r = requests.get(f"{base_url}/rest/api/content/{page_id}", params={'expand': 'body.storage'}, auth=auth)
        r.raise_for_status()
        content = r.json().get('body', {}).get('storage', {}).get('value', '')
        # Optionally convert from storage format to Markdown
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(content, "lxml")
        content = soup.get_text("\n")
    else:
        # Assume file path
        if not os.path.exists(doc_source):
            raise FileNotFoundError(f"File not found: {doc_source}")
        with open(doc_source, "r", encoding="utf-8") as f:
            content = f.read()
    # Compose prompt
    full_prompt = prompt.format(content=content)
    # Call LLM
    if llm_call is None:
        raise ValueError("llm_call function must be provided")
    summary = llm_call(full_prompt)
    return summary

def extract_metadata_from_summary(summary, llm_call, cache_path="cache/ai_metadata.json"):
    """
    Use an LLM to extract structured metadata from a document summary, and update cached lists of categories, clients, technologies, services, and document types.
    Returns the metadata dict.
    """
    prompt = '''You are an expert information architect and knowledge graph engineer.
Given the following summary of a Confluence document, extract and output a structured set of metadata fields that will make this document easily searchable and filterable by both humans and LLMs.

For the summary below, extract:
- Title: (If available or inferable)
- One-sentence Purpose: (If not already present, infer it)
- Topics: List of main topics or subjects covered (as keywords/phrases)
- Categories: Broad categories or tags (e.g., "DevOps", "HR", "Product", "Support", "Security", etc.)
- Clients/Stakeholders: Any client, team, or stakeholder names mentioned or implied
- Technologies/Tools: Any technologies, programming languages, platforms, or tools referenced
- Services/Products: Any services, products, or solutions discussed
- Document Type: (e.g., "How-To", "Design Doc", "Meeting Notes", "Policy", "Reference", "Release Notes", etc.)
- Action Items/Decisions: (If present, list them)
- Other Notable Entities: (Any other important named entities, e.g., locations, regulations, standards)

Output Format:
- Use valid JSON.
- Each field should be a string or a list of strings (as appropriate).
- If a field is not present or not inferable, use an empty list or null.

---

Document Summary:
```
{summary}
```
'''
    full_prompt = prompt.format(summary=summary)
    metadata_json = llm_call(full_prompt)
    # Parse JSON output
    try:
        metadata = json.loads(metadata_json)
    except Exception as e:
        raise ValueError(f"LLM did not return valid JSON: {e}\nOutput: {metadata_json}")
    # Update cached lists
    cache_dir = os.path.dirname(cache_path)
    os.makedirs(cache_dir, exist_ok=True)
    if os.path.exists(cache_path):
        with open(cache_path, "r", encoding="utf-8") as f:
            ai_cache = json.load(f)
    else:
        ai_cache = {"categories": [], "clients": [], "technologies": [], "services": [], "document_types": []}
    def update_list(key, new_values):
        if not isinstance(new_values, list):
            new_values = [new_values] if new_values else []
        ai_cache[key] = sorted(list(set(ai_cache.get(key, []) + [v for v in new_values if v and v not in ai_cache.get(key, [])])))
    update_list("categories", metadata.get("categories", []))
    update_list("clients", metadata.get("clients", []))
    update_list("technologies", metadata.get("technologies", []))
    update_list("services", metadata.get("services", []))
    update_list("document_types", [metadata.get("document_type")] if metadata.get("document_type") else [])
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(ai_cache, f, indent=2)
    return metadata

def refine_and_report_metadata(llm_call, summary_metadata, generated_summary, original_doc_metadata, cache_path="cache/ai_metadata.json", report_path="cache/refined_metadata_report.json"):
    """
    Intention: This function refines the cached AI-generated metadata lists (categories, clients, technologies, services, document_types) into more generic, normalized versions using an LLM. It then generates a report associating the refined metadata with the summary metadata, the generated summary, and the original document metadata. The report is saved for later analysis or review.
    """
    # Step 1: Load cached lists
    if not os.path.exists(cache_path):
        raise FileNotFoundError(f"Metadata cache not found: {cache_path}")
    with open(cache_path, "r", encoding="utf-8") as f:
        ai_cache = json.load(f)
    # Step 2: LLM prompt to refine lists
    prompt = f'''
You are an expert information architect and taxonomy specialist.
Given the following lists of categories, clients, technologies, services, and document types (as generated by an AI from a large set of documents), refine each list by grouping similar or synonymous items, removing duplicates, and generalizing overly specific entries into broader, more useful categories. Output a new JSON object with the same keys, but with each list containing only the most generic, normalized, and useful values for search, filtering, and analytics.

Input Metadata Lists:
{json.dumps(ai_cache, indent=2)}

Output Format:
- Use valid JSON.
- Each field should be a list of strings (no empty strings, no duplicates).
- Use generic, normalized, and human-friendly values.
'''
    refined_json = llm_call(prompt)
    try:
        refined_metadata = json.loads(refined_json)
    except Exception as e:
        raise ValueError(f"LLM did not return valid JSON: {e}\nOutput: {refined_json}")
    # Step 3: Generate report
    report = {
        "refined_metadata": refined_metadata,
        "summary_metadata": summary_metadata,
        "generated_summary": generated_summary,
        "original_doc_metadata": original_doc_metadata
    }
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    return report

def check_llm_server_health(llm_server_url="http://localhost:5051"):
    """Check if the LLM server is healthy. Returns True if healthy, False otherwise."""
    import requests
    try:
        resp = requests.get(f"{llm_server_url}/health", timeout=5)
        if resp.status_code == 200 and resp.json().get("status") == "ok":
            return True
        print(f"[WARN] LLM server health check failed: {resp.status_code} {resp.text}")
        return False
    except Exception as e:
        print(f"[WARN] LLM server health check error: {e}")
        return False

def process_space_with_llm_cache(space_key, base_url, auth, space_cache_path, llm_server_url="http://localhost:5051", batch_size=5, dry_run=False, search_query=None, rate_limit_delay=2):
    """
    For each document in a space, create a cached LLM data structure:
    {reference, summary, metadata_from_summary, refined_metadata}
    Writes intermediate results to cache after each step (summary, metadata, refinement).
    For maximum speed, consider using async HTTP for LLM calls or increasing batch_size, but beware of LLM server overload.
    """
    import os, json, time
    from datetime import datetime
    error_log_path = os.path.join("cache", f"llm_{space_key}_errors.log")
    if not check_llm_server_health(llm_server_url):
        print(f"[ERROR] LLM server at {llm_server_url} is not healthy. Aborting batch.")
        return {"space_key": space_key, "error": "LLM server not healthy"}
    with open(space_cache_path, "r", encoding="utf-8") as f:
        crawl_cache = json.load(f)
    page_ids = crawl_cache.get("processed_ids") or list(crawl_cache.get("page_metadata", {}).keys())
    page_metadata = crawl_cache.get("page_metadata", {})
    llm_cache_dir = os.path.join("cache", f"llm_{space_key}")
    os.makedirs(llm_cache_dir, exist_ok=True)
    processed, skipped, errors = [], [], []
    def robust_llm_post(url, payload, context):
        tries = 0
        while tries < 5:
            try:
                resp = requests.post(url, json=payload)
                if resp.status_code == 429 or (resp.status_code == 503 and 'overload' in resp.text.lower()):
                    print(f"[WARN] LLM server rate limited or overloaded. Sleeping {rate_limit_delay}s...")
                    time.sleep(rate_limit_delay)
                    tries += 1
                    continue
                resp.raise_for_status()
                return resp.json().get("result", "")
            except Exception as e:
                err_msg = f"[{datetime.now()}] LLM POST error ({context}): {e} (status: {getattr(resp, 'status_code', 'N/A')})\nPayload: {json.dumps(payload)[:200]}...\n"
                with open(error_log_path, "a", encoding="utf-8") as logf:
                    logf.write(err_msg)
                print(f"[ERROR] {err_msg.strip()}")
                tries += 1
                time.sleep(rate_limit_delay)
        return f"[ERROR: LLM server failed after {tries} attempts]"
    def process_page(page_id):
        doc_ref = {"space_key": space_key, "page_id": page_id}
        llm_cache_path = os.path.join(llm_cache_dir, f"{page_id}.json")
        if os.path.exists(llm_cache_path):
            skipped.append(page_id)
            return None
        if dry_run:
            return {"reference": doc_ref, "summary": "[DRY RUN]", "metadata_from_summary": "[DRY RUN]", "refined_metadata": "[DRY RUN]"}
        # Pass 1: Summarize
        doc_source = f"https://{base_url}/pages/{page_id}"
        summary = robust_llm_post(f"{llm_server_url}/llm/generate", {
            "prompt": f"Summarize the following Confluence page:",
            "context": doc_source,
            "model": "llama3.3"
        }, context=f"summarize {page_id}")
        # Write after summary
        llm_data = {"reference": doc_ref, "summary": summary}
        with open(llm_cache_path, "w", encoding="utf-8") as f:
            json.dump(llm_data, f, indent=2)
        # Pass 2: Extract metadata from summary
        metadata_from_summary = robust_llm_post(f"{llm_server_url}/llm/generate", {
            "prompt": "Extract structured metadata from the following summary:",
            "context": summary,
            "model": "llama3.3"
        }, context=f"metadata {page_id}")
        llm_data["metadata_from_summary"] = metadata_from_summary
        with open(llm_cache_path, "w", encoding="utf-8") as f:
            json.dump(llm_data, f, indent=2)
        # Pass 3: Refine metadata
        refined_metadata = robust_llm_post(f"{llm_server_url}/llm/generate", {
            "prompt": "Refine and generalize the following metadata for analytics:",
            "context": metadata_from_summary,
            "model": "llama3.3"
        }, context=f"refine {page_id}")
        llm_data["refined_metadata"] = refined_metadata
        with open(llm_cache_path, "w", encoding="utf-8") as f:
            json.dump(llm_data, f, indent=2)
        processed.append(page_id)
        return llm_data
    from tqdm import tqdm
    from concurrent.futures import ThreadPoolExecutor, as_completed
    with ThreadPoolExecutor(max_workers=batch_size) as executor:
        futures = {executor.submit(process_page, pid): pid for pid in page_ids}
        for f in tqdm(as_completed(futures), total=len(page_ids), desc=f"Processing {space_key}"):
            try:
                f.result()
            except Exception as e:
                pid = futures[f]
                errors.append((pid, str(e)))
                with open(error_log_path, "a", encoding="utf-8") as logf:
                    logf.write(f"[{datetime.now()}] Error processing {pid}: {e}\n")
    summary = {
        "space_key": space_key,
        "total": len(page_ids),
        "processed": processed,
        "skipped": skipped,
        "errors": errors,
        "llm_cache_dir": llm_cache_dir
    }
    return summary

def generate_redundancy_similarity_report(space_key, llm_server_url="http://localhost:5051", output_path=None):
    """
    Generate a report of likely redundant or similar documents for a single space using LLM cache, metadata, and LLM semantic similarity.
    Only includes pages listed in the crawl cache for that space.
    Writes a Markdown report listing groups of likely redundant pages with explanations.
    """
    import os, json
    from collections import defaultdict
    if not space_key:
        print("[WARN] No space_key provided for redundancy report.")
        return None
    crawl_cache_path = f"cache/{space_key}_crawl_cache.json"
    llm_cache_dir = os.path.join("cache", f"llm_{space_key}")
    if not os.path.exists(crawl_cache_path) or not os.path.isdir(llm_cache_dir):
        print(f"[WARN] Missing crawl cache or LLM cache for space {space_key}.")
        return None
    with open(crawl_cache_path, "r", encoding="utf-8") as f:
        crawl_cache = json.load(f)
    page_ids = set(crawl_cache.get("processed_ids") or list(crawl_cache.get("page_metadata", {}).keys()))
    files = [os.path.join(llm_cache_dir, f"{pid}.json") for pid in page_ids if os.path.exists(os.path.join(llm_cache_dir, f"{pid}.json"))]
    docs = []
    for fpath in files:
        with open(fpath, "r", encoding="utf-8") as f:
            doc = json.load(f)
            doc["_cache_path"] = fpath
            docs.append(doc)
    # Group by title and document type for initial redundancy
    groups = defaultdict(list)
    for doc in docs:
        title = doc.get("metadata_from_summary", {}).get("title") or doc.get("summary", "")[:40]
        doc_type = doc.get("metadata_from_summary", {}).get("document_type") or "Unknown"
        key = (title.strip().lower(), doc_type.strip().lower())
        groups[key].append(doc)
    # Use LLM to check for semantic similarity within groups with >1 doc
    redundant_groups = []
    for key, group in groups.items():
        if len(group) < 2:
            continue
        prompt = """You are a documentation analyst. Given the following list of Confluence documents (with summaries and metadata), identify which are likely redundant or near-duplicates. Group them and explain why. Output as Markdown table with columns: Page Title, Page ID, Reason for Redundancy, Document Type.

Documents:
"""
        for doc in group:
            prompt += f"\n- Title: {doc.get('metadata_from_summary', {}).get('title', '[No Title]')}\n  Page ID: {doc['reference']['page_id']}\n  Summary: {doc.get('summary', '')}\n  Metadata: {json.dumps(doc.get('metadata_from_summary', {}))}\n"
        prompt += "\n---\nOutput:"
        try:
            resp = requests.post(f"{llm_server_url}/llm/generate", json={
                "prompt": prompt,
                "model": "llama3.3"
            })
            resp.raise_for_status()
            llm_result = resp.json().get("result", "")
        except Exception as e:
            llm_result = f"[ERROR: {e}]"
        redundant_groups.append(llm_result)
    if not output_path:
        output_path = f"reports/{space_key}_redundancy_similarity_report.md"
    os.makedirs("reports", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"# Redundancy & Similarity Report for Space {space_key}\n\n")
        if not redundant_groups:
            f.write("No likely redundant documents found.\n")
        else:
            for group_md in redundant_groups:
                f.write(group_md + "\n\n")
    return output_path

def generate_coverage_heatmap(space_key, output_path=None):
    """
    Generate a heatmap of documentation coverage by category/topic/document_type for a single space using LLM cache metadata.
    Only includes pages listed in the crawl cache for that space.
    Writes a Markdown table heatmap.
    """
    import os, json
    from collections import Counter
    import glob
    if not space_key:
        print("[WARN] No space_key provided for coverage heatmap.")
        return None
    crawl_cache_path = f"cache/{space_key}_crawl_cache.json"
    llm_cache_dir = os.path.join("cache", f"llm_{space_key}")
    if not os.path.exists(crawl_cache_path) or not os.path.isdir(llm_cache_dir):
        print(f"[WARN] Missing crawl cache or LLM cache for space {space_key}.")
        return None
    with open(crawl_cache_path, "r", encoding="utf-8") as f:
        crawl_cache = json.load(f)
    page_ids = set(crawl_cache.get("processed_ids") or list(crawl_cache.get("page_metadata", {}).keys()))
    files = [os.path.join(llm_cache_dir, f"{pid}.json") for pid in page_ids if os.path.exists(os.path.join(llm_cache_dir, f"{pid}.json"))]
    cat_counter = Counter()
    topic_counter = Counter()
    type_counter = Counter()
    for fpath in files:
        with open(fpath, "r", encoding="utf-8") as f:
            doc = json.load(f)
            meta = doc.get("metadata_from_summary", {})
            for cat in meta.get("categories", []) or []:
                cat_counter[cat] += 1
            for topic in meta.get("topics", []) or []:
                topic_counter[topic] += 1
            dtype = meta.get("document_type")
            if dtype:
                type_counter[dtype] += 1
    if not output_path:
        output_path = f"reports/{space_key}_coverage_heatmap.md"
    os.makedirs("reports", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"# Documentation Coverage Heatmap for Space {space_key}\n\n")
        f.write("## By Category\n\n| Category | # Docs |\n|---|---|\n")
        for cat, count in cat_counter.most_common():
            f.write(f"| {cat} | {count} |\n")
        f.write("\n## By Topic\n\n| Topic | # Docs |\n|---|---|\n")
        for topic, count in topic_counter.most_common():
            f.write(f"| {topic} | {count} |\n")
        f.write("\n## By Document Type\n\n| Document Type | # Docs |\n|---|---|\n")
        for dtype, count in type_counter.most_common():
            f.write(f"| {dtype} | {count} |\n")
    return output_path 