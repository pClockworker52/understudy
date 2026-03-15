"""
Cloud Run backend using Google GenAI SDK.
Proxies prediction + analysis requests to Vertex AI.
"""

import os
import json
import time
import logging
import base64
from flask import Flask, request, jsonify
from google import genai
from google.genai import types

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# Initialize GenAI client with Vertex AI
# This satisfies: GenAI SDK + Google Cloud service (Vertex AI) + Cloud Run hosting
client = genai.Client(
    vertexai=True,
    project=os.environ.get("GOOGLE_CLOUD_PROJECT"),
    location=os.environ.get("VERTEX_LOCATION", "us-central1"),
)

NO_THINKING = types.GenerateContentConfig(
    thinking_config=types.ThinkingConfig(thinking_budget=0)
)


@app.route("/predict", methods=["POST"])
def predict():
    """Handle prediction requests from desktop client."""
    t0 = time.time()
    data = request.json

    prompt = data.get("prompt", "")
    image_b64 = data.get("image")  # base64 string from client

    contents = [prompt]
    if image_b64:
        image_bytes = base64.b64decode(image_b64)
        contents.append(types.Part.from_bytes(data=image_bytes, mime_type='image/jpeg'))

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=contents,
            config=NO_THINKING,
        )
        latency_ms = int((time.time() - t0) * 1000)
        logging.info(json.dumps({"event": "predict", "latency_ms": latency_ms}))
        return jsonify({"response": response.text, "latency_ms": latency_ms})
    except Exception as e:
        logging.error(f"Prediction error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/analyze-session", methods=["POST"])
def analyze_session():
    """Analyze session logs for workflow patterns."""
    t0 = time.time()
    data = request.json

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[data.get("prompt", "")],
            config=NO_THINKING,
        )
        latency_ms = int((time.time() - t0) * 1000)
        logging.info(json.dumps({"event": "analyze", "latency_ms": latency_ms}))
        return jsonify({"response": response.text, "latency_ms": latency_ms})
    except Exception as e:
        logging.error(f"Analysis error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy", "model": "gemini-2.5-flash"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
