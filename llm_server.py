"""
llm_server.py
-------------
A Flask server that acts as an entry point for local LLM (Ollama) inference.
- POST /llm/generate: Accepts prompt, context, data, and optional model ('llama3.3', 'llama3.2', 'codellama'); sends to Ollama; returns result.
- GET /health: Health check endpoint.

Start/stop independently using CLI (see server_manager.py for pattern).
"""
from flask import Flask, request, jsonify
import requests
import os
import logging

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
DEFAULT_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.3")
ALLOWED_MODELS = {"llama3.3", "llama3.2", "codellama"}

# Setup logging
logger = logging.getLogger("llm_server")
if not logger.hasHandlers():
    handler = logging.FileHandler("llm_server.log")
    formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

app = Flask(__name__)

logger.info("LLM server starting up.")
print("[LLM SERVER] Starting up...")

def call_ollama(prompt, model=DEFAULT_MODEL):
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False
    }
    logger.info(f"Calling Ollama: model={model}, prompt_len={len(prompt)}")
    resp = requests.post(f"{OLLAMA_URL}/api/generate", json=payload)
    resp.raise_for_status()
    return resp.json().get("response", "")

@app.route('/llm/generate', methods=['POST'])
def llm_generate():
    data = request.json
    prompt = data.get("prompt", "")
    context = data.get("context", "")
    extra_data = data.get("data", "")
    model = data.get("model", DEFAULT_MODEL)
    logger.info(f"/llm/generate request: model={model}, prompt_len={len(prompt)}, context_len={len(context)}, data_len={len(extra_data)}")
    if model not in ALLOWED_MODELS:
        logger.warning(f"Unsupported model requested: {model}")
        return jsonify({"error": f"Model '{model}' not supported. Allowed: {sorted(ALLOWED_MODELS)}"}), 400
    full_prompt = prompt
    if context:
        full_prompt += f"\n\nContext:\n{context}"
    if extra_data:
        full_prompt += f"\n\nData:\n{extra_data}"
    try:
        result = call_ollama(full_prompt, model=model)
        logger.info(f"LLM call successful. Result len: {len(result)}")
        return jsonify({"result": result}), 200
    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    logger.info("Health check requested.")
    return jsonify({"status": "ok"}), 200

if __name__ == '__main__':
    port = int(os.environ.get('LLM_SERVER_PORT', 5051))
    logger.info(f"LLM server running on port {port}")
    print(f"[LLM SERVER] Running on port {port}")
    app.run(port=port, debug=True) 