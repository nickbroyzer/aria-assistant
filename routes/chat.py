"""
Chat blueprint — public-facing chatbot and appointment booking.

Routes:
  /                        → index page
  /widget                  → widget page
  /name                    → POST set visitor name
  /chat                    → POST streaming chat (SSE)
  /update-memory           → POST extract user facts
  /extract-lead            → POST extract lead from conversation
  /suggest-prompts         → POST generate follow-up suggestions
  /available-slots         → GET calendar availability
  /book-appointment        → POST book Google Calendar event
"""

import base64
import json
import re
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import anthropic
import requests
from flask import Blueprint, Response, jsonify, render_template, request, stream_with_context

_anthropic = anthropic.Anthropic()          # uses ANTHROPIC_API_KEY env var
_MODEL = "claude-sonnet-4-6"

from utils.constants import (
    ASSISTANT_NAME, GMAIL_APP_PASSWORD, GMAIL_SENDER, SYSTEM_PROMPT,
)
from utils.config import _integ_val
from utils.memory import (
    get_user_memory, load_memory, save_memory, update_user_memory,
)
from utils.search import process_pdf, web_search
from utils.calendar import get_available_slots, get_calendar_service, _get_calendar_id

chat_bp = Blueprint("chat", __name__)


# ── Pages ─────────────────────────────────────────────────────────────────────

@chat_bp.route("/")
def index():
    memory = load_memory()
    name = memory.get("name")
    return render_template("index.html", name=name, assistant_name=ASSISTANT_NAME)


@chat_bp.route("/widget")
def widget():
    memory = load_memory()
    name = memory.get("name")
    return render_template("index.html", name=name, assistant_name=ASSISTANT_NAME)


@chat_bp.route("/name", methods=["POST"])
def set_name():
    name = request.json.get("name", "").strip()
    if not name:
        return {"error": "Name required"}, 400
    memory = load_memory()
    memory["name"] = name
    save_memory(memory)
    return {"ok": True}


# ── Streaming chat ────────────────────────────────────────────────────────────

@chat_bp.route("/chat", methods=["POST"])
def chat():
    data = request.get_json() or {}
    messages = data.get("messages", [])
    memory = load_memory()
    name = memory.get("name", "there")

    system_prompt = SYSTEM_PROMPT.format(name=name)

    # Inject returning user memory if available
    if name and name != "there":
        user_mem = get_user_memory(name)
        if user_mem and user_mem.get("sessions", 0) > 0:
            mem_lines = []
            if user_mem.get("company"):
                mem_lines.append(f"Company: {user_mem['company']}")
            if user_mem.get("location"):
                mem_lines.append(f"Location: {user_mem['location']}")
            if user_mem.get("interests"):
                mem_lines.append(f"Interested in: {', '.join(user_mem['interests'])}")
            if user_mem.get("notes"):
                mem_lines.append(f"Past context: {user_mem['notes']}")
            if user_mem.get("last_seen"):
                mem_lines.append(f"Last visited: {user_mem['last_seen']}")
            if mem_lines:
                system_prompt += (
                    f"\n\nReturning customer context for {name}:\n"
                    + "\n".join(mem_lines)
                    + "\nReference this naturally when relevant — welcome them back "
                    "and pick up where they left off."
                )

    image_data = data.get("image")   # { base64, mime_type }
    pdf_data = data.get("pdf")       # { base64 }

    def analyze_image_with_claude(img_b64: str, mime_type: str, prompt: str) -> str:
        """Send an image to Claude and return the analysis."""
        resp = _anthropic.messages.create(
            model=_MODEL,
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": mime_type, "data": img_b64}},
                    {"type": "text", "text": prompt},
                ],
            }],
        )
        return resp.content[0].text

    def generate():
        try:
            VISION_PROMPT = (
                "You are analyzing a warehouse photo or floor plan for a warehouse "
                "installation company. Describe in detail what you see: the layout, "
                "existing equipment (racking, conveyors, cranes, doors, docks, "
                "offices, etc.), condition, approximate size, and any obvious issues "
                "or opportunities for improvement. Be specific and thorough."
            )

            image_context = ""
            if image_data:
                analysis = analyze_image_with_claude(
                    image_data["base64"],
                    image_data.get("mime_type", "image/jpeg"),
                    VISION_PROMPT,
                )
                image_context = (
                    "\n\nImage analysis of the photo the customer uploaded:\n"
                    + analysis + "\n"
                )

            if pdf_data:
                yield 'data: {"status": "reading"}\n\n'
                pdf_bytes = base64.b64decode(pdf_data["base64"])
                pdf = process_pdf(pdf_bytes)
                if pdf.get("text"):
                    image_context += (
                        "\n\nPDF uploaded by the customer — extracted text:\n"
                        + pdf["text"] + "\n"
                    )
                else:
                    image_context += (
                        "\n\nThe customer uploaded a PDF but no text could be "
                        "extracted (may be image-only).\n"
                    )

            # Pre-search: search based on the latest user message
            user_query = ""
            for msg in messages:
                if msg.get("role") == "user":
                    user_query = msg.get("content", "")

            search_context = ""
            if user_query and user_query != "Please analyze this image.":
                yield 'data: {"status": "searching"}\n\n'
                search_results = web_search(user_query)
                if search_results and "Search failed" not in search_results:
                    search_context = (
                        f"\n\nCurrent web search results for context:\n"
                        f"{search_results}\n"
                    )

            yield 'data: {"status": "thinking"}\n\n'

            enriched_system = system_prompt + image_context + search_context

            claude_messages = []
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if content:
                    claude_messages.append({"role": role, "content": content})

            with _anthropic.messages.stream(
                model=_MODEL,
                max_tokens=1024,
                system=enriched_system,
                messages=claude_messages,
            ) as stream:
                for text in stream.text_stream:
                    if text:
                        text = re.sub(
                            r'<web_search>.*?</web_search>', '', text,
                            flags=re.DOTALL,
                        )
                        text = re.sub(
                            r'<[a-z_]+>.*?</[a-z_]+>', '', text,
                            flags=re.DOTALL,
                        )
                        if text:
                            yield f"data: {json.dumps(text)}\n\n"

            yield "data: [DONE]\n\n"

        except Exception as e:
            yield f"data: {json.dumps('Error: ' + str(e))}\n\n"
            yield "data: [DONE]\n\n"

    return Response(stream_with_context(generate()), mimetype="text/event-stream")


# ── Memory / lead extraction / prompt suggestions ─────────────────────────────

@chat_bp.route("/update-memory", methods=["POST"])
def update_memory():
    """Extract and persist key facts about the user from the conversation."""
    data = request.get_json() or {}
    msgs = data.get("messages", [])
    memory = load_memory()
    name = memory.get("name", "")

    if not name or not msgs:
        return jsonify({"ok": False})

    conversation = "\n".join(
        f"{m['role'].upper()}: {m['content']}" for m in msgs if m.get("content")
    )

    prompt = (
        "Extract key facts about the customer from this conversation. "
        "Return ONLY valid JSON:\n"
        '{\n  "company": "",\n  "location": "",\n  "interests": [],\n  "notes": ""\n}\n'
        "- interests: list of services/topics they asked about "
        '(e.g. ["pallet racking", "mezzanines"])\n'
        "- notes: 1-2 sentence summary of what they're looking for\n"
        "- Leave fields empty if not mentioned. Do not guess.\n\n"
        f"Conversation:\n{conversation}"
    )

    try:
        resp = _anthropic.messages.create(
            model=_MODEL, max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        content = resp.content[0].text
        match = re.search(r'\{.*\}', content, re.DOTALL)
        if match:
            facts = json.loads(match.group())
            update_user_memory(name, facts)
            return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

    return jsonify({"ok": False})


@chat_bp.route("/extract-lead", methods=["POST"])
def extract_lead():
    """Use the model to extract lead info from the conversation."""
    data = request.get_json() or {}
    msgs = data.get("messages", [])

    if not msgs:
        return jsonify({"found": False})

    conversation = "\n".join(
        f"{m['role'].upper()}: {m['content']}" for m in msgs if m.get("content")
    )

    prompt = (
        "Extract lead information from this conversation. Return ONLY valid JSON "
        "with these fields:\n"
        '{\n  "name": "",\n  "company": "",\n  "location": "",\n  '
        '"contact": "",\n  "project_details": ""\n}\n'
        "Leave a field empty string if not mentioned. Do not guess or infer — "
        "only use what was explicitly stated.\n\n"
        f"Conversation:\n{conversation}"
    )

    try:
        resp = _anthropic.messages.create(
            model=_MODEL, max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        content = resp.content[0].text

        match = re.search(r'\{.*\}', content, re.DOTALL)
        if not match:
            return jsonify({"found": False})

        extracted = json.loads(match.group())
        has_data = any(extracted.get(f) for f in ["name", "contact", "project_details"])
        if not has_data:
            return jsonify({"found": False})

        return jsonify({"found": True, "lead": extracted})

    except Exception as e:
        return jsonify({"found": False, "error": str(e)})


@chat_bp.route("/suggest-prompts", methods=["POST"])
def suggest_prompts():
    """Generate 3 context-aware follow-up prompt suggestions."""
    data = request.get_json() or {}
    msgs = data.get("messages", [])

    if not msgs:
        return jsonify({"prompts": []})

    conversation = "\n".join(
        f"{m['role'].upper()}: {m['content']}" for m in msgs[-6:] if m.get("content")
    )

    prompt = (
        "Based on this conversation with a Pacific Construction warehouse "
        "installation assistant, suggest exactly 3 short follow-up questions a "
        "customer might want to ask next. Make them specific, natural, and "
        "relevant to the conversation context.\n\n"
        "Return ONLY a JSON array of 3 strings. No explanation, no markdown, "
        "just the array. Example:\n"
        '["How much does pallet racking cost?", '
        '"How long does installation take?", "Do you handle permits?"]\n\n'
        f"Conversation:\n{conversation}"
    )

    try:
        resp = _anthropic.messages.create(
            model=_MODEL, max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )
        content = resp.content[0].text

        match = re.search(r'\[.*?\]', content, re.DOTALL)
        if not match:
            return jsonify({"prompts": []})

        prompts = json.loads(match.group())
        return jsonify({"prompts": prompts[:3]})

    except Exception as e:
        return jsonify({"prompts": [], "error": str(e)})


# ── Appointment booking ──────────────────────────────────────────────────────

@chat_bp.route("/available-slots", methods=["GET"])
def available_slots():
    """Return available appointment slots."""
    try:
        slots = get_available_slots()
        return jsonify({"slots": slots})
    except Exception as e:
        return jsonify({"slots": [], "error": str(e)})


@chat_bp.route("/book-appointment", methods=["POST"])
def book_appointment():
    """Book an appointment on Google Calendar and notify both parties."""
    data = request.get_json() or {}
    name = data.get("name", "").strip()
    email = data.get("email", "").strip()
    phone = data.get("phone", "").strip()
    slot_start = data.get("slot_start", "").strip()
    slot_end = data.get("slot_end", "").strip()
    appt_type = data.get("type", "Quote / Site Visit").strip()
    notes = data.get("notes", "").strip()

    if not name or not slot_start or not slot_end:
        return jsonify({"error": "Name and slot are required"}), 400

    try:
        service = get_calendar_service()
        event = {
            "summary": f"Pacific Construction — {appt_type}: {name}",
            "description": (
                f"Customer: {name}\nEmail: {email}\nPhone: {phone}\nNotes: {notes}"
            ),
            "start": {"dateTime": slot_start, "timeZone": "America/Los_Angeles"},
            "end": {"dateTime": slot_end, "timeZone": "America/Los_Angeles"},
        }
        if email:
            event["attendees"] = [{"email": email}]
        created = service.events().insert(
            calendarId=_get_calendar_id(), body=event, sendUpdates="all",
        ).execute()

        # Confirmation email to customer
        if email:
            dt = datetime.fromisoformat(slot_start)
            label = (
                dt.strftime("%A, %B %d at %I:%M %p").replace(" 0", " ")
                + " (Pacific Time)"
            )
            try:
                msg = MIMEMultipart("alternative")
                msg["Subject"] = "Appointment Confirmed — Pacific Construction"
                msg["From"] = f"Pacific Construction <{GMAIL_SENDER}>"
                msg["To"] = email
                first = name.split()[0]
                body = (
                    f"Hi {first},\n\n"
                    "Your appointment with Pacific Construction is confirmed!\n\n"
                    f"  Type:    {appt_type}\n"
                    f"  Date:    {label}\n"
                    "  Phone:   253.826.2727\n"
                    "  Address: 1574 Thornton Ave SW, Pacific, WA 98047\n\n"
                    "If you need to reschedule, please call us at 253.826.2727.\n\n"
                    "— The Pacific Construction Team\n"
                )
                html = (
                    '<html><body style="font-family:Arial,sans-serif;color:#222;'
                    'max-width:600px;margin:auto;">'
                    '<div style="background:#1a3a5c;padding:24px 32px;">'
                    '<h2 style="color:#fff;margin:0;">Pacific Construction</h2>'
                    '<p style="color:#a8c4e0;margin:4px 0 0;">Warehouse Installation '
                    "Specialists</p></div>"
                    '<div style="padding:32px;">'
                    f"<p>Hi {first},</p>"
                    "<p>Your appointment with <strong>Pacific Construction</strong> "
                    "is confirmed!</p>"
                    '<table style="margin:16px 0;border-collapse:collapse;">'
                    '<tr><td style="padding:4px 12px 4px 0;color:#666;">Type</td>'
                    f"<td><strong>{appt_type}</strong></td></tr>"
                    '<tr><td style="padding:4px 12px 4px 0;color:#666;">Date</td>'
                    f"<td><strong>{label}</strong></td></tr>"
                    '<tr><td style="padding:4px 12px 4px 0;color:#666;">Phone</td>'
                    "<td>253.826.2727</td></tr>"
                    '<tr><td style="padding:4px 12px 4px 0;color:#666;">Address</td>'
                    "<td>1574 Thornton Ave SW, Pacific, WA 98047</td></tr>"
                    "</table>"
                    "<p>If you need to reschedule, please call us at "
                    "<strong>253.826.2727</strong>.</p>"
                    '<p style="margin-top:32px;color:#666;">'
                    "— The Pacific Construction Team</p></div>"
                    '<div style="background:#f4f4f4;padding:12px 32px;font-size:12px;'
                    'color:#999;">Pacific Construction · 1574 Thornton Ave SW, Pacific, '
                    "WA 98047 · 253.826.2727</div></body></html>"
                )
                msg.attach(MIMEText(body, "plain"))
                msg.attach(MIMEText(html, "html"))
                with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                    server.login(GMAIL_SENDER, GMAIL_APP_PASSWORD)
                    server.sendmail(GMAIL_SENDER, email, msg.as_string())
            except Exception as e:
                print(f"Confirmation email failed: {e}")

        return jsonify({
            "ok": True,
            "event_id": created.get("id"),
            "event_link": created.get("htmlLink"),
        }), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500
