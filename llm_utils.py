"""
llm_utils.py
------------
Utilities for combining files using an LLM (OpenAI API) for the Confluence Downloader project.
"""
import openai
import os

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
    combined_content = ""
    # Read and concatenate all file contents, separating with headers
    for file_path in file_paths:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                file_content = f.read()
            combined_content += f"\n\n---\n\n# {os.path.basename(file_path)}\n\n" + file_content
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
    # Set the OpenAI API key
    openai.api_key = api_key
    try:
        # Call the OpenAI chat completion API
        response = openai.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a helpful technical writer."},
                {"role": "user", "content": prompt + "\n\n" + combined_content}
            ],
            max_tokens=4096  # adjust as needed
        )
        llm_output = response.choices[0].message.content
    except Exception as e:
        print(f"Error calling OpenAI API: {e}")
        return None
    # Write the LLM's output to the specified Markdown file
    output_path = os.path.join(output_dir, output_filename)
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(llm_output)
    except Exception as e:
        print(f"Error writing LLM-combined file: {e}")
        return None
    return output_path 