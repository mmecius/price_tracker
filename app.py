from flask import Flask, render_template, request, jsonify
import anthropic
import json
import re
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Prefer explicit API key; fall back to Claude Code session token (Bearer auth)
_api_key    = os.getenv("ANTHROPIC_API_KEY")
_token_file = os.getenv("CLAUDE_SESSION_INGRESS_TOKEN_FILE", "")
_auth_token = None
if not _api_key and _token_file:
    try:
        with open(_token_file) as _f:
            _auth_token = _f.read().strip()
    except OSError:
        pass

if _auth_token:
    client = anthropic.Anthropic(auth_token=_auth_token)
else:
    client = anthropic.Anthropic(api_key=_api_key)  # raises if None

DENTAL_PARSE_TOOL = {
    "name": "parse_dental_note",
    "description": "Parse a dentist's spoken note and extract structured tooth data using FDI numbering.",
    "input_schema": {
        "type": "object",
        "properties": {
            "teeth": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {
                            "type": "string",
                            "description": "FDI tooth number as string, e.g. '16', '21', '48'"
                        },
                        "condition": {
                            "type": "string",
                            "enum": [
                                "cavity", "filling", "crown", "extraction",
                                "missing", "healthy", "crack", "pain",
                                "sensitivity", "root_canal", "bridge",
                                "implant", "observation"
                            ]
                        },
                        "description": {
                            "type": "string",
                            "description": "Short clinical description of the finding"
                        },
                        "severity": {
                            "type": "string",
                            "enum": ["mild", "moderate", "severe", "n/a"]
                        }
                    },
                    "required": ["id", "condition", "description", "severity"]
                }
            },
            "summary": {
                "type": "string",
                "description": "One-sentence clinical summary of all findings"
            }
        },
        "required": ["teeth", "summary"]
    }
}

SYSTEM_PROMPT = """You are a dental assistant AI that parses dentist voice notes.
Convert spoken dental observations into structured data using FDI tooth numbering.

FDI numbering (quadrant + position):
• Upper right Q1: 11 12 13 14 15 16 17 18  (11=central incisor … 18=wisdom)
• Upper left  Q2: 21 22 23 24 25 26 27 28
• Lower left  Q3: 31 32 33 34 35 36 37 38
• Lower right Q4: 41 42 43 44 45 46 47 48

Name→FDI mapping examples:
  "upper right first molar" → 16
  "lower left canine"       → 33
  "tooth 6" (Universal)    → 26 (upper left first molar)

Accept input in English, Lithuanian, German, Russian, or Polish.
Always call parse_dental_note with every tooth mentioned."""


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/process", methods=["POST"])
def process():
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()

    if not text:
        return jsonify({"teeth": [], "summary": "No text provided."})

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=[DENTAL_PARSE_TOOL],
            tool_choice={"type": "auto"},
            messages=[{"role": "user", "content": text}],
            extra_headers={"anthropic-beta": "prompt-caching-2024-07-31"},
        )

        for block in response.content:
            if block.type == "tool_use" and block.name == "parse_dental_note":
                return jsonify(block.input)

        # Fallback: try to pull JSON from plain text response
        raw = next(
            (b.text for b in response.content if hasattr(b, "text")), ""
        )
        m = re.search(r"\{[\s\S]+\}", raw)
        if m:
            return jsonify(json.loads(m.group()))

        return jsonify({"teeth": [], "summary": raw or "No findings extracted."})

    except anthropic.APIError as e:
        return jsonify({"error": str(e), "teeth": [], "summary": "API error."}), 500
    except Exception as e:
        return jsonify({"error": str(e), "teeth": [], "summary": "Server error."}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5000)
