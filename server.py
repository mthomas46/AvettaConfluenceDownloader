from flask import Flask, request, jsonify
import os
from confluence_api import summarize_confluence_document, extract_metadata_from_summary, get_all_spaces

app = Flask(__name__)

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"}), 200

@app.route('/llm/summarize', methods=['POST'])
def llm_summarize():
    data = request.json
    doc_source = data.get('doc_source')
    base_url = data.get('base_url')
    auth = tuple(data.get('auth', []))
    # Placeholder: expects llm_call to be injected or mocked
    def dummy_llm_call(prompt):
        return "[LLM summary would go here]"
    try:
        summary = summarize_confluence_document(doc_source, base_url, auth, llm_call=dummy_llm_call)
        return jsonify({"summary": summary}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/llm/metadata', methods=['POST'])
def llm_metadata():
    data = request.json
    summary = data.get('summary')
    # Placeholder: expects llm_call to be injected or mocked
    def dummy_llm_call(prompt):
        return '{"categories": ["Example"], "clients": [], "technologies": [], "services": [], "document_types": ["How-To"]}'
    try:
        metadata = extract_metadata_from_summary(summary, llm_call=dummy_llm_call)
        return jsonify(metadata), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/confluence/crawl', methods=['POST'])
def confluence_crawl():
    data = request.json
    space_key = data.get('space_key')
    # Placeholder: actual crawl logic should be called here
    # For now, just return a dummy response
    return jsonify({"status": "crawl started", "space_key": space_key}), 202

@app.route('/confluence/space/<space_key>', methods=['GET'])
def get_space_metadata(space_key):
    # Return cached metadata for a space (dummy for now)
    return jsonify({"space_key": space_key, "metadata": "[cached metadata would go here]"}), 200

@app.route('/confluence/page/<page_id>', methods=['GET'])
def get_page_metadata(page_id):
    # Return cached metadata for a page (dummy for now)
    return jsonify({"page_id": page_id, "metadata": "[cached page metadata would go here]"}), 200

@app.route('/confluence/search', methods=['GET'])
def search_metadata():
    query = request.args.get('q', '')
    # Placeholder: search cached metadata (dummy for now)
    return jsonify({"query": query, "results": []}), 200

if __name__ == '__main__':
    port = int(os.environ.get('CONFLUENCE_API_PORT', 5050))
    app.run(port=port, debug=True) 