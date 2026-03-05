import json
import os

import anthropic
from flask import Flask, Response, render_template, request, stream_with_context

MEMORY_FILE = "memory.json"
ASSISTANT_NAME = "Ash"

SYSTEM_PROMPT = """You are Ash, the friendly virtual assistant for Pacific Construction, a warehouse installation company based in Pacific, WA. Pacific Construction serves customers throughout Washington, Oregon, Idaho, Alaska, and California.

Contact information:
- Phone: 253.826.2727
- Address: 1574 Thornton Ave SW, Pacific, WA 98047

Services Pacific Construction offers:
- Pallet racking systems (new installations, reconfiguration, expansion)
- Conveyor systems
- Bridge cranes
- Mezzanines
- Modular offices
- Dock equipment (dock levelers, bumpers, seals, shelters)
- Warehouse doors (overhead, roll-up, high-speed)
- Safety railing
- Security cages
- Welding and custom fabrication
- Maintenance programs
- Damaged rack assessments
- Permitting assistance

Your role is to help visitors learn about Pacific Construction's services, answer questions, and capture leads for the sales team.

Your style:
- Friendly, helpful, and professional
- Give clear, useful answers — don't make visitors work hard to get information
- When someone is ready to move forward, direct them to call 253.826.2727 or visit 1574 Thornton Ave SW, Pacific, WA 98047
- For quotes and site visits, always encourage them to call or come in

When capturing leads, try to naturally learn the visitor's name, company, location, and what they're looking for so the sales team has context when they follow up.

The user's name is {name}."""

app = Flask(__name__, static_folder="static")
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
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
