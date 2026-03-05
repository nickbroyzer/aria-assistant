import json
import os

import anthropic
from flask import Flask, Response, render_template, request, stream_with_context

MEMORY_FILE = "memory.json"
ASSISTANT_NAME = "Aria"

SYSTEM_PROMPT = """You are Aria, a friendly and professional AI integration consultant specializing in helping small businesses adopt and get the most out of AI tools.

Your areas of expertise include:
- Recommending the right AI tools for specific business needs (marketing, customer service, operations, finance, etc.)
- Explaining AI concepts in plain, accessible language — no jargon unless asked
- Helping businesses evaluate AI tools based on budget, team size, and technical skill level
- Advising on implementation strategies, change management, and measuring ROI
- Staying current on popular tools like ChatGPT, Claude, Notion AI, Zapier, HubSpot AI, and many others

Your style:
- Warm, encouraging, and approachable — small business owners may feel intimidated by AI
- Practical and actionable — focus on real-world impact, not hype
- Honest about limitations and tradeoffs of different tools
- Always tailor advice to the specific business context

The user's name is {name}."""

app = Flask(__name__)
client = anthropic.Anthropic()


def load_memory():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE) as f:
            return json.load(f)
    return {}


def save_memory(data):
    with open(MEMORY_FILE, "w") as f:
        json.dump(data, f)


@app.route("/")
def index():
    memory = load_memory()
    name = memory.get("name")
    return render_template("index.html", name=name, assistant_name=ASSISTANT_NAME)


@app.route("/name", methods=["POST"])
def set_name():
    name = request.json.get("name", "").strip()
    if not name:
        return {"error": "Name required"}, 400
    memory = load_memory()
    memory["name"] = name
    save_memory(memory)
    return {"ok": True}


@app.route("/chat", methods=["POST"])
def chat():
    data = request.json
    messages = data.get("messages", [])
    memory = load_memory()
    name = memory.get("name", "there")

    def generate():
        with client.messages.stream(
            model="claude-opus-4-6",
            max_tokens=1024,
            system=SYSTEM_PROMPT.format(name=name),
            messages=messages,
        ) as stream:
            for text in stream.text_stream:
                yield f"data: {json.dumps(text)}\n\n"
        yield "data: [DONE]\n\n"

    return Response(stream_with_context(generate()), mimetype="text/event-stream")


if __name__ == "__main__":
    app.run(debug=True)
