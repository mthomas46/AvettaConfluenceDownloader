"""
llm_utils.py
------------
Utilities for combining files using an LLM (OpenAI API) for the Confluence Downloader project.
"""
import openai
import os
from tqdm import tqdm
import time
from itertools import cycle

def combine_files_with_llm(file_paths, output_dir, api_key, model="gpt-4", output_filename="LLM_Combined.md"):
    """
    Combine the given files using an LLM and save the result as a Markdown file.

    Args:
        file_paths (list): List of file paths to combine.
        output_dir (str): Directory to save the combined file.
        api_key (str): OpenAI API key.
        model (str): OpenAI model to use (default: gpt-4).
        output_filename (str): Name of the output Markdown file.
    Returns:
        str: Path to the combined Markdown file, or None on error.
    """
    # The prompt instructs the LLM to combine, deduplicate, and improve the content
    prompt = (
        "combine these files into 1. preserve all unique information. "
        "improve readability and flow. create sections and reorder information based on need and where applicable"
    )
    print("\n[LLM] Preparing to read files for combination...")
    combined_content = ""
    # Read and concatenate all file contents, separating with headers
    for file_path in tqdm(file_paths, desc="Reading files for LLM combine"):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                file_content = f.read()
            combined_content += f"\n\n---\n\n# {os.path.basename(file_path)}\n\n" + file_content
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
    print("[LLM] Finished reading and preparing files.")
    # Set the OpenAI API key
    openai.api_key = api_key
    try:
        print("[LLM] Sending content to OpenAI for combination. This may take a few moments...")
        # Show a spinner while waiting for the API call
        import threading
        stop_spinner = False
        def spinner():
            for c in cycle(['|', '/', '-', '\\']):
                if stop_spinner:
                    break
                print(f'\r[LLM] Waiting for OpenAI response... {c}', end='', flush=True)
                time.sleep(0.1)
            print('\r', end='', flush=True)
        spinner_thread = threading.Thread(target=spinner)
        spinner_thread.start()
        # Call the OpenAI chat completion API
        response = openai.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a helpful technical writer."},
                {"role": "user", "content": prompt + "\n\n" + combined_content}
            ],
            max_tokens=4096  # adjust as needed
        )
        stop_spinner = True
        spinner_thread.join()
        print("[LLM] Received response from OpenAI.")
        llm_output = response.choices[0].message.content
    except Exception as e:
        print(f"Error calling OpenAI API: {e}")
        return None
    # Write the LLM's output to the specified Markdown file
    output_path = os.path.join(output_dir, output_filename)
    try:
        print(f"[LLM] Writing combined content to {output_path} ...")
        for _ in tqdm(range(20), desc="Writing file", ncols=70):
            time.sleep(0.01)  # Simulate progress for user feedback
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(llm_output)
        print(f"[LLM] Successfully wrote combined file: {output_path}")
    except Exception as e:
        print(f"Error writing LLM-combined file: {e}")
        return None
    return output_path 