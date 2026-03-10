import base64
import io
import json
import os
import re
import smtplib
import threading
import uuid
from datetime import date, datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from dotenv import load_dotenv
load_dotenv()

import fitz  # PyMuPDF
import pdfplumber
import requests
from duckduckgo_search import DDGS
from flask import Flask, Response, g, jsonify, render_template, request, session, stream_with_context
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from file_locks import file_lock

MEMORY_FILE = "memory.json"
LEADS_FILE = "leads.jsonl"
USER_SESSIONS_FILE = "user_sessions.json"
ASSISTANT_NAME = "Ash"

# Gmail config
GMAIL_SENDER = os.getenv("GMAIL_SENDER")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
LEAD_NOTIFY_EMAIL = os.getenv("LEAD_NOTIFY_EMAIL")  # Update to Jay's email when ready
SHEETS_WEBHOOK = os.getenv("SHEETS_WEBHOOK")
DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "")


def send_lead_email(lead: dict):
    """Send a lead notification email via Gmail SMTP."""
    try:
        msg = MIMEMultipart("alternative")
        score = lead.get('score', '')
        msg["Subject"] = f"{score} New Lead from Ash — {lead.get('name') or 'Unknown'}"
        msg["From"] = GMAIL_SENDER
        msg["To"] = LEAD_NOTIFY_EMAIL

        body = f"""
New lead captured by Ash — Pacific Construction virtual assistant.

Lead Score:      {lead.get('score') or '—'}
Name:            {lead.get('name') or '—'}
Company:         {lead.get('company') or '—'}
Location:        {lead.get('location') or '—'}
Contact:         {lead.get('contact') or '—'}
Project Details: {lead.get('project_details') or '—'}
Source:          {lead.get('source') or 'chat'}
Time:            {lead.get('timestamp') or '—'}
Lead ID:         {lead.get('lead_id') or '—'}
"""
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_SENDER, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_SENDER, LEAD_NOTIFY_EMAIL, msg.as_string())
    except Exception as e:
        print(f"Email notification failed: {e}")

SYSTEM_PROMPT = """You are Ash, the friendly virtual assistant for Pacific Construction, a warehouse installation company based in Pacific, WA.

CRITICAL: For all facts about Pacific Construction (owner, contact info, services, location), only use the information provided in this prompt — never use your training data.

For general industry questions (OSHA regulations, product specs, industry standards, pricing, how-to questions, etc.), web search results will be provided to you automatically in the context. Use those results to give accurate, up-to-date answers. Do NOT output any XML tags, tool call syntax, or search queries in your response — just answer naturally using the information provided.

Pacific Construction is owned by Jay Farber. Do not state any other name as the owner under any circumstances.

The company serves customers throughout Washington, Oregon, Idaho, Alaska, and California. It has over 35 years of experience and is one of the largest material handling installers in the Northwest.

Contact information:
- Owner: Jay Farber
- Phone: 253.826.2727
- Address: 1574 Thornton Ave SW, Pacific, WA 98047

Services Pacific Construction offers:
- Pallet racking systems (new installations, reconfiguration, expansion)
- Conveyor systems
- Bridge cranes
- Mezzanines
- Modular offices
- Pick modules
- Shelving
- Material lifts / VRC (vertical reciprocating conveyors)
- Wire guidance systems
- Warehouse curtains
- Dock equipment (dock levelers, bumpers, seals, shelters)
- Warehouse doors (overhead, roll-up, high-speed)
- Safety railing
- Security cages
- Welding and custom fabrication
- Tenant improvement
- Maintenance programs
- Damaged rack assessments
- Permitting assistance

Your role is to help visitors learn about Pacific Construction's services, answer questions, and capture leads for the sales team.

Your style:
- Friendly, helpful, and professional
- Give clear, useful answers — don't make visitors work hard to get information
- Always refer to the company as "Pacific Construction" or "our team" — never refer to individuals by name (e.g. don't say "Jay will..." — say "Pacific Construction will..." or "our team will...")
- When someone is ready to move forward, direct them to call 253.826.2727 or visit 1574 Thornton Ave SW, Pacific, WA 98047
- For quotes and site visits, always encourage them to call or come in

When capturing leads, try to naturally learn the visitor's name, company, location, and what they're looking for so the sales team has context when they follow up.

The user's name is {name}."""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for current information about products, industry standards, pricing, or anything not covered in your system prompt. Use this to give accurate, up-to-date answers.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query"
                    }
                },
                "required": ["query"]
            }
        }
    }
]


def web_search(query: str, max_results: int = 5) -> str:
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        if not results:
            return "No results found."
        formatted = []
        for r in results:
            formatted.append(f"Title: {r['title']}\nSummary: {r['body']}\nSource: {r['href']}")
        return "\n\n".join(formatted)
    except Exception as e:
        return f"Search failed: {str(e)}"


def process_pdf(pdf_bytes: bytes) -> dict:
    """Extract text and/or render pages as images from a PDF.
    Returns { text, images: [base64, ...] }
    """
    # Extract text
    text = ""
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            pages_text = [p.extract_text() or "" for p in pdf.pages]
            text = "\n\n".join(pages_text).strip()
    except Exception:
        pass

    # Render pages as images (up to 4 pages)
    images = []
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        for i, page in enumerate(doc):
            if i >= 4:
                break
            mat = fitz.Matrix(1.5, 1.5)  # 1.5x zoom for clarity
            pix = page.get_pixmap(matrix=mat)
            img_bytes = pix.tobytes("png")
            images.append(base64.b64encode(img_bytes).decode("utf-8"))
        doc.close()
    except Exception:
        pass

    return {"text": text, "images": images}


app = Flask(__name__, static_folder="static")
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.secret_key = os.getenv("SECRET_KEY", "")
if not app.secret_key:
    raise RuntimeError("SECRET_KEY environment variable is required. Set it in .env")

USERS_FILE = "users.json"


def load_users():
    if os.path.exists(USERS_FILE):
        with file_lock(USERS_FILE):
            with open(USERS_FILE) as f:
                return json.load(f).get("users", [])
    return []


def save_users(users_list):
    with file_lock(USERS_FILE):
        with open(USERS_FILE, "w") as f:
            json.dump({"users": users_list}, f, indent=2)


def get_current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    users = load_users()
    return next((u for u in users if u["user_id"] == uid and u.get("active", True)), None)


def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not get_current_user() and session.get("user_id") != "owner-jay":
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated


def require_owner(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not user or user.get("role") not in ("owner", "admin"):
            return jsonify({"error": "Forbidden"}), 403
        return f(*args, **kwargs)
    return decorated


def load_memory():
    if os.path.exists(MEMORY_FILE):
        with file_lock(MEMORY_FILE):
            with open(MEMORY_FILE) as f:
                return json.load(f)
    return {}


def save_memory(data):
    with file_lock(MEMORY_FILE):
        with open(MEMORY_FILE, "w") as f:
            json.dump(data, f)


def load_user_sessions():
    if os.path.exists(USER_SESSIONS_FILE):
        with file_lock(USER_SESSIONS_FILE):
            with open(USER_SESSIONS_FILE) as f:
                return json.load(f)
    return {}


def save_user_sessions(data):
    with file_lock(USER_SESSIONS_FILE):
        with open(USER_SESSIONS_FILE, "w") as f:
            json.dump(data, f, indent=2)


def get_user_memory(name: str) -> dict:
    sessions = load_user_sessions()
    return sessions.get(name.lower().strip(), {})


def update_user_memory(name: str, facts: dict):
    sessions = load_user_sessions()
    key = name.lower().strip()
    existing = sessions.get(key, {})
    existing.update({k: v for k, v in facts.items() if v})
    existing["sessions"] = existing.get("sessions", 0) + 1
    existing["last_seen"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    sessions[key] = existing
    save_user_sessions(sessions)


def score_lead(lead: dict) -> str:
    """Score a lead as Hot, Warm, or Cold based on available info."""
    score = 0
    details = (lead.get("project_details") or "").lower()
    contact = (lead.get("contact") or "").lower()
    email = (lead.get("email") or "").lower()
    phone = (lead.get("phone") or "").lower()

    # Has contact info
    if email or "@" in contact:
        score += 2
    if phone or any(c.isdigit() for c in contact):
        score += 2

    # Has company name
    if lead.get("company"):
        score += 1

    # Has location
    if lead.get("location"):
        score += 1

    # Project details quality
    if len(details) > 50:
        score += 2
    elif len(details) > 20:
        score += 1

    # Urgency keywords
    urgent_words = ["urgent", "asap", "immediately", "this week", "next week", "ready", "now", "quote", "start"]
    if any(w in details for w in urgent_words):
        score += 3

    # Large project keywords
    large_words = ["sq ft", "square feet", "pallet position", "5,000", "10,000", "20,000", "warehouse", "facility", "distribution"]
    if any(w in details for w in large_words):
        score += 2

    if score >= 8:
        return "🔥 Hot"
    elif score >= 4:
        return "⚡ Warm"
    else:
        return "❄️ Cold"


def extract_email_phone(contact: str):
    """Split a contact string into email and phone."""
    import re
    email = ""
    phone = ""
    if contact:
        email_match = re.search(r'[\w.+-]+@[\w-]+\.[a-zA-Z]+', contact)
        phone_match = re.search(r'[\d\s\-\.\(\)\+]{7,}', contact)
        if email_match:
            email = email_match.group()
        if phone_match:
            phone = phone_match.group().strip()
    return email, phone


def send_followup_email(lead: dict):
    """Send a branded follow-up email directly to the lead."""
    email, _ = extract_email_phone(lead.get("contact", ""))
    email = lead.get("email") or email
    if not email:
        return  # No email address to send to

    name = lead.get("name") or "there"
    first_name = name.split()[0] if name else "there"

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Thanks for reaching out — Pacific Construction"
        msg["From"] = f"Pacific Construction <{GMAIL_SENDER}>"
        msg["To"] = email

        body = f"""Hi {first_name},

Thank you for contacting Pacific Construction! We received your inquiry and our team will be in touch shortly.

In the meantime, if you have any urgent questions, feel free to reach us directly:

  Phone:   253.826.2727
  Address: 1574 Thornton Ave SW, Pacific, WA 98047

We look forward to working with you.

— The Pacific Construction Team
"""
        html = f"""<html><body style="font-family:Arial,sans-serif;color:#222;max-width:600px;margin:auto;">
<div style="background:#1a3a5c;padding:24px 32px;">
  <h2 style="color:#fff;margin:0;">Pacific Construction</h2>
  <p style="color:#a8c4e0;margin:4px 0 0;">Warehouse Installation Specialists</p>
</div>
<div style="padding:32px;">
  <p>Hi {first_name},</p>
  <p>Thank you for reaching out to <strong>Pacific Construction</strong>! We received your inquiry and our team will be in touch shortly.</p>
  <p>In the meantime, if you have any urgent questions:</p>
  <table style="margin:16px 0;border-collapse:collapse;">
    <tr><td style="padding:4px 12px 4px 0;color:#666;">Phone</td><td><strong>253.826.2727</strong></td></tr>
    <tr><td style="padding:4px 12px 4px 0;color:#666;">Address</td><td>1574 Thornton Ave SW, Pacific, WA 98047</td></tr>
  </table>
  <p>We look forward to working with you.</p>
  <p style="margin-top:32px;color:#666;">— The Pacific Construction Team</p>
</div>
<div style="background:#f4f4f4;padding:12px 32px;font-size:12px;color:#999;">
  Pacific Construction · 1574 Thornton Ave SW, Pacific, WA 98047 · 253.826.2727
</div>
</body></html>"""

        msg.attach(MIMEText(body, "plain"))
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_SENDER, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_SENDER, email, msg.as_string())
        print(f"Follow-up email sent to {email}")
    except Exception as e:
        print(f"Follow-up email failed: {e}")


def load_leads():
    """Load all leads from the JSONL file with file locking."""
    leads = []
    if os.path.exists(LEADS_FILE):
        with file_lock(LEADS_FILE):
            with open(LEADS_FILE, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            leads.append(json.loads(line))
                        except Exception:
                            pass
    return leads

def append_lead(lead_data):
    """Append a lead to the JSON Lines file and log to Google Sheets."""
    with file_lock(LEADS_FILE):
        with open(LEADS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(lead_data, default=str) + "\n")
    if SHEETS_WEBHOOK:
        try:
            # Use explicit email/phone if provided, otherwise extract from contact
            email = lead_data.get("email", "")
            phone = lead_data.get("phone", "")
            if not email and not phone:
                email, phone = extract_email_phone(lead_data.get("contact", ""))
            sheets_data = {**lead_data, "email": email, "phone": phone, "score": lead_data.get("score", "")}
            requests.post(SHEETS_WEBHOOK, json=sheets_data, timeout=10)
        except Exception as e:
            print(f"Sheets logging failed: {e}")


@app.route("/")
def index():
    memory = load_memory()
    name = memory.get("name")
    return render_template("index.html", name=name, assistant_name=ASSISTANT_NAME)


@app.route("/widget")
def widget():
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
                system_prompt += f"\n\nReturning customer context for {name}:\n" + "\n".join(mem_lines) + "\nReference this naturally when relevant — welcome them back and pick up where they left off."

    image_data = data.get("image")  # { base64, mime_type }
    pdf_data = data.get("pdf")    # { base64 }

    def analyze_images_with_llava(image_b64_list: list, prompt: str) -> str:
        """Send one or more images to llava and return the analysis."""
        results = []
        for img_b64 in image_b64_list:
            vision_payload = {
                "model": "llava",
                "messages": [{
                    "role": "user",
                    "content": prompt,
                    "images": [img_b64],
                }],
                "stream": False,
            }
            r = requests.post("http://localhost:11434/api/chat", json=vision_payload, timeout=120)
            r.raise_for_status()
            results.append(r.json().get("message", {}).get("content", ""))
        return "\n\n".join(results)

    def generate():
        try:
            VISION_PROMPT = (
                "You are analyzing a warehouse photo or floor plan for a warehouse installation company. "
                "Describe in detail what you see: the layout, existing equipment (racking, conveyors, cranes, "
                "doors, docks, offices, etc.), condition, approximate size, and any obvious issues or "
                "opportunities for improvement. Be specific and thorough."
            )

            # If an image was uploaded, analyze it with llava first
            image_context = ""
            if image_data:
                analysis = analyze_images_with_llava([image_data["base64"]], VISION_PROMPT)
                image_context = "\n\nImage analysis of the photo the customer uploaded:\n" + analysis + "\n"

            # If a PDF was uploaded, process it (text extraction only)
            if pdf_data:
                yield 'data: {"status": "reading"}\n\n'
                pdf_bytes = base64.b64decode(pdf_data["base64"])
                pdf = process_pdf(pdf_bytes)

                if pdf.get("text"):
                    image_context += "\n\nPDF uploaded by the customer — extracted text:\n" + pdf["text"] + "\n"
                else:
                    image_context += "\n\nThe customer uploaded a PDF but no text could be extracted (may be image-only).\n"

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
                    search_context = f"\n\nCurrent web search results for context:\n{search_results}\n"

            yield 'data: {"status": "thinking"}\n\n'

            # Build messages with enriched system prompt
            enriched_system = system_prompt + image_context + search_context
            ollama_messages = []
            if enriched_system:
                ollama_messages.append({"role": "system", "content": enriched_system})

            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if content:
                    ollama_messages.append({"role": role, "content": content})

            payload = {
                "model": "kimi-k2:1t-cloud",
                "messages": ollama_messages,
                "stream": True,
            }

            with requests.post(
                "http://localhost:11434/api/chat",
                json=payload,
                stream=True,
                timeout=120,
            ) as r:
                r.raise_for_status()
                for line in r.iter_lines():
                    if not line:
                        continue
                    chunk = json.loads(line.decode("utf-8"))
                    content = chunk.get("message", {}).get("content", "")
                    if content:
                        # Strip any XML-style tool call tags the model might emit
                        content = re.sub(r'<web_search>.*?</web_search>', '', content, flags=re.DOTALL)
                        content = re.sub(r'<[a-z_]+>.*?</[a-z_]+>', '', content, flags=re.DOTALL)
                        if content:
                            yield f"data: {json.dumps(content)}\n\n"

            yield "data: [DONE]\n\n"

        except Exception as e:
            yield f"data: {json.dumps('Error: ' + str(e))}\n\n"
            yield "data: [DONE]\n\n"

    return Response(stream_with_context(generate()), mimetype="text/event-stream")


@app.route("/lead", methods=["POST"])
def capture_lead():
    """Capture a lead from the chat.

    Requires at least one of: name, contact, or project_details.
    Generates lead_id and timestamp server-side.
    """
    data = request.get_json() or {}

    name = data.get("name", "").strip()
    company = data.get("company", "").strip()
    location = data.get("location", "").strip()
    contact = data.get("contact", "").strip()
    project_details = data.get("project_details", "").strip()
    source = data.get("source", "chat").strip()

    # Require at least one of: name, contact, or project_details
    if not name and not contact and not project_details:
        return jsonify({
            "error": "At least one of name, contact, or project_details is required"
        }), 400

    # Load session name from memory if available
    memory = load_memory()
    session_name = memory.get("name")

    lead = {
        "lead_id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "name": name,
        "company": company,
        "location": location,
        "contact": contact,
        "project_details": project_details,
        "source": source,
        "session_name": session_name
    }
    lead["score"] = score_lead(lead)

    try:
        append_lead(lead)
        # Initialize lead meta with "new" status
        meta = load_lead_meta()
        meta[lead["lead_id"]] = {"status": "new", "created_at": lead["timestamp"]}
        save_lead_meta(meta)
        send_lead_email(lead)
        send_followup_email(lead)
        threading.Thread(target=start_lead_nurture_sequence, args=(lead,), daemon=True).start()
        return jsonify({
            "ok": True,
            "lead_id": lead["lead_id"],
            "message": "Lead captured successfully"
        }), 201
    except Exception as e:
        return jsonify({
            "error": f"Failed to save lead: {str(e)}"
        }), 500


@app.route("/quote", methods=["POST"])
def submit_quote():
    """Handle a structured quote request form submission."""
    data = request.get_json() or {}

    name = data.get("name", "").strip()
    email = data.get("email", "").strip()

    if not name or not email:
        return jsonify({"error": "Name and email are required"}), 400

    # Save as a lead
    lead = {
        "lead_id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "name": name,
        "company": data.get("company", "").strip(),
        "location": data.get("location", "").strip(),
        "contact": f"{email}" + (f" | {data.get('phone','').strip()}" if data.get("phone") else ""),
        "email": email,
        "phone": data.get("phone", "").strip(),
        "project_details": (
            f"Service: {data.get('service','')}, "
            f"Size: {data.get('warehouse_size','')} sq ft, "
            f"Height: {data.get('clear_height','')}, "
            f"Timeline: {data.get('timeline','')}, "
            f"Notes: {data.get('notes','')}"
        ),
        "source": "quote-form",
        "session_name": name,
    }
    lead["score"] = score_lead(lead)
    append_lead(lead)

    # Send detailed quote email
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Quote Request — {name} | {data.get('service','') or 'General'}"
        msg["From"] = GMAIL_SENDER
        msg["To"] = LEAD_NOTIFY_EMAIL

        body = f"""
New quote request submitted via the Pacific Construction chatbot.

CONTACT INFORMATION
───────────────────
Name:     {name}
Company:  {data.get('company') or '—'}
Email:    {email}
Phone:    {data.get('phone') or '—'}

PROJECT DETAILS
───────────────────
Location:        {data.get('location') or '—'}
Warehouse Size:  {data.get('warehouse_size') or '—'} sq ft
Clear Height:    {data.get('clear_height') or '—'}
Service Needed:  {data.get('service') or '—'}
Timeline:        {data.get('timeline') or '—'}

ADDITIONAL NOTES
───────────────────
{data.get('notes') or 'None'}

───────────────────
Lead ID:   {lead['lead_id']}
Submitted: {lead['timestamp']}
"""
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_SENDER, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_SENDER, LEAD_NOTIFY_EMAIL, msg.as_string())
    except Exception as e:
        print(f"Quote email failed: {e}")

    send_followup_email(lead)
    return jsonify({"ok": True}), 201


@app.route("/update-memory", methods=["POST"])
def update_memory():
    """Extract and persist key facts about the user from the conversation."""
    data = request.get_json() or {}
    messages = data.get("messages", [])
    memory = load_memory()
    name = memory.get("name", "")

    if not name or not messages:
        return jsonify({"ok": False})

    conversation = "\n".join(
        f"{m['role'].upper()}: {m['content']}" for m in messages if m.get("content")
    )

    prompt = f"""Extract key facts about the customer from this conversation. Return ONLY valid JSON:
{{
  "company": "",
  "location": "",
  "interests": [],
  "notes": ""
}}
- interests: list of services/topics they asked about (e.g. ["pallet racking", "mezzanines"])
- notes: 1-2 sentence summary of what they're looking for
- Leave fields empty if not mentioned. Do not guess.

Conversation:
{conversation}"""

    try:
        r = requests.post("http://localhost:11434/api/chat", json={
            "model": "kimi-k2:1t-cloud",
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        }, timeout=30)
        r.raise_for_status()
        content = r.json().get("message", {}).get("content", "")
        match = re.search(r'\{.*\}', content, re.DOTALL)
        if match:
            facts = json.loads(match.group())
            update_user_memory(name, facts)
            return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

    return jsonify({"ok": False})


@app.route("/extract-lead", methods=["POST"])
def extract_lead():
    """Use the model to extract lead info from the conversation and auto-capture if found."""
    data = request.get_json() or {}
    messages = data.get("messages", [])

    if not messages:
        return jsonify({"found": False})

    conversation = "\n".join(
        f"{m['role'].upper()}: {m['content']}" for m in messages if m.get("content")
    )

    prompt = f"""Extract lead information from this conversation. Return ONLY valid JSON with these fields:
{{
  "name": "",
  "company": "",
  "location": "",
  "contact": "",
  "project_details": ""
}}
Leave a field empty string if not mentioned. Do not guess or infer — only use what was explicitly stated.

Conversation:
{conversation}"""

    try:
        r = requests.post("http://localhost:11434/api/chat", json={
            "model": "kimi-k2:1t-cloud",
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        }, timeout=30)
        r.raise_for_status()
        content = r.json().get("message", {}).get("content", "")

        # Extract JSON from response
        match = re.search(r'\{.*\}', content, re.DOTALL)
        if not match:
            return jsonify({"found": False})

        extracted = json.loads(match.group())

        # Only capture if at least one meaningful field present
        has_data = any(extracted.get(f) for f in ["name", "contact", "project_details"])
        if not has_data:
            return jsonify({"found": False})

        return jsonify({"found": True, "lead": extracted})

    except Exception as e:
        return jsonify({"found": False, "error": str(e)})


@app.route("/suggest-prompts", methods=["POST"])
def suggest_prompts():
    """Generate 3 context-aware follow-up prompt suggestions based on the conversation."""
    data = request.get_json() or {}
    messages = data.get("messages", [])

    if not messages:
        return jsonify({"prompts": []})

    conversation = "\n".join(
        f"{m['role'].upper()}: {m['content']}" for m in messages[-6:] if m.get("content")
    )

    prompt = f"""Based on this conversation with a Pacific Construction warehouse installation assistant, suggest exactly 3 short follow-up questions a customer might want to ask next. Make them specific, natural, and relevant to the conversation context.

Return ONLY a JSON array of 3 strings. No explanation, no markdown, just the array. Example:
["How much does pallet racking cost?", "How long does installation take?", "Do you handle permits?"]

Conversation:
{conversation}"""

    try:
        r = requests.post("http://localhost:11434/api/chat", json={
            "model": "kimi-k2:1t-cloud",
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        }, timeout=30)
        r.raise_for_status()
        content = r.json().get("message", {}).get("content", "")

        match = re.search(r'\[.*?\]', content, re.DOTALL)
        if not match:
            return jsonify({"prompts": []})

        prompts = json.loads(match.group())
        return jsonify({"prompts": prompts[:3]})

    except Exception as e:
        return jsonify({"prompts": [], "error": str(e)})


def _get_calendar_id():
    return _integ_val("CALENDAR_ID") or "primary"
CALENDAR_TOKEN = "google_token.json"
CALENDAR_CREDS = "google_credentials.json"
CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar"]
BUSINESS_HOURS = {"start": 8, "end": 17}  # 8am–5pm
SLOT_DURATION = 60  # minutes


def get_calendar_service():
    """Return an authorized Google Calendar service."""
    creds = None
    if os.path.exists(CALENDAR_TOKEN):
        creds = Credentials.from_authorized_user_file(CALENDAR_TOKEN, CALENDAR_SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(CALENDAR_TOKEN, "w") as f:
            f.write(creds.to_json())
    return build("calendar", "v3", credentials=creds)


def get_available_slots(days_ahead=7):
    """Return available 1-hour slots over the next N weekdays during business hours."""
    service = get_calendar_service()
    now = datetime.now(timezone.utc)
    end_range = now + timedelta(days=days_ahead * 2)  # extra buffer for weekends

    # Fetch existing events
    events_result = service.events().list(
        calendarId=_get_calendar_id(),
        timeMin=now.isoformat(),
        timeMax=end_range.isoformat(),
        singleEvents=True,
        orderBy="startTime"
    ).execute()
    busy = []
    for e in events_result.get("items", []):
        s = e.get("start", {}).get("dateTime")
        en = e.get("end", {}).get("dateTime")
        if s and en:
            busy.append((datetime.fromisoformat(s), datetime.fromisoformat(en)))

    # Generate candidate slots
    slots = []
    pacific = timezone(timedelta(hours=-7))  # PDT (Pacific Daylight)
    day = datetime.now(pacific).replace(hour=0, minute=0, second=0, microsecond=0)
    days_found = 0
    while days_found < days_ahead:
        day += timedelta(days=1)
        if day.weekday() >= 5:  # skip weekends
            continue
        days_found += 1
        for hour in range(BUSINESS_HOURS["start"], BUSINESS_HOURS["end"]):
            slot_start = day.replace(hour=hour, minute=0, second=0, microsecond=0)
            slot_end = slot_start + timedelta(hours=1)
            slot_start_utc = slot_start.astimezone(timezone.utc)
            slot_end_utc = slot_end.astimezone(timezone.utc)
            # Check for conflicts
            conflict = any(
                s < slot_end_utc and e > slot_start_utc for s, e in busy
            )
            if not conflict:
                slots.append({
                    "start": slot_start.isoformat(),
                    "end": slot_end.isoformat(),
                    "label": slot_start.strftime("%A, %B %d · %I:%M %p").replace(" 0", " ")
                })
    return slots[:10]  # return up to 10 slots


@app.route("/available-slots", methods=["GET"])
def available_slots():
    """Return available appointment slots."""
    try:
        slots = get_available_slots()
        return jsonify({"slots": slots})
    except Exception as e:
        return jsonify({"slots": [], "error": str(e)})


@app.route("/book-appointment", methods=["POST"])
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
            "description": f"Customer: {name}\nEmail: {email}\nPhone: {phone}\nNotes: {notes}",
            "start": {"dateTime": slot_start, "timeZone": "America/Los_Angeles"},
            "end": {"dateTime": slot_end, "timeZone": "America/Los_Angeles"},
        }
        if email:
            event["attendees"] = [{"email": email}]
        created = service.events().insert(calendarId=_get_calendar_id(), body=event, sendUpdates="all").execute()

        # Confirmation email to customer
        if email:
            dt = datetime.fromisoformat(slot_start)
            label = dt.strftime("%A, %B %d at %I:%M %p").replace(" 0", " ") + " (Pacific Time)"
            try:
                msg = MIMEMultipart("alternative")
                msg["Subject"] = f"Appointment Confirmed — Pacific Construction"
                msg["From"] = f"Pacific Construction <{GMAIL_SENDER}>"
                msg["To"] = email
                first = name.split()[0]
                body = f"""Hi {first},

Your appointment with Pacific Construction is confirmed!

  Type:    {appt_type}
  Date:    {label}
  Phone:   253.826.2727
  Address: 1574 Thornton Ave SW, Pacific, WA 98047

If you need to reschedule, please call us at 253.826.2727.

— The Pacific Construction Team
"""
                html = f"""<html><body style="font-family:Arial,sans-serif;color:#222;max-width:600px;margin:auto;">
<div style="background:#1a3a5c;padding:24px 32px;">
  <h2 style="color:#fff;margin:0;">Pacific Construction</h2>
  <p style="color:#a8c4e0;margin:4px 0 0;">Warehouse Installation Specialists</p>
</div>
<div style="padding:32px;">
  <p>Hi {first},</p>
  <p>Your appointment with <strong>Pacific Construction</strong> is confirmed!</p>
  <table style="margin:16px 0;border-collapse:collapse;">
    <tr><td style="padding:4px 12px 4px 0;color:#666;">Type</td><td><strong>{appt_type}</strong></td></tr>
    <tr><td style="padding:4px 12px 4px 0;color:#666;">Date</td><td><strong>{label}</strong></td></tr>
    <tr><td style="padding:4px 12px 4px 0;color:#666;">Phone</td><td>253.826.2727</td></tr>
    <tr><td style="padding:4px 12px 4px 0;color:#666;">Address</td><td>1574 Thornton Ave SW, Pacific, WA 98047</td></tr>
  </table>
  <p>If you need to reschedule, please call us at <strong>253.826.2727</strong>.</p>
  <p style="margin-top:32px;color:#666;">— The Pacific Construction Team</p>
</div>
<div style="background:#f4f4f4;padding:12px 32px;font-size:12px;color:#999;">
  Pacific Construction · 1574 Thornton Ave SW, Pacific, WA 98047 · 253.826.2727
</div>
</body></html>"""
                msg.attach(MIMEText(body, "plain"))
                msg.attach(MIMEText(html, "html"))
                with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                    server.login(GMAIL_SENDER, GMAIL_APP_PASSWORD)
                    server.sendmail(GMAIL_SENDER, email, msg.as_string())
            except Exception as e:
                print(f"Confirmation email failed: {e}")

        return jsonify({"ok": True, "event_id": created.get("id"), "event_link": created.get("htmlLink")}), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500


JOBS_FILE = "jobs.json"
INVOICES_FILE = "invoices.json"
JOBCOSTS_FILE = "jobcosts.json"
PEOPLE_FILE  = "people.json"
CONFIG_FILE  = "config.json"
ACTIVITY_FILE = "activity_log.jsonl"

def log_activity(action: str, description: str, meta: dict = None):
    """Append a timestamped activity event to the activity log."""
    user = get_current_user()
    if user:
        actor = user.get("name") or user.get("username") or "Unknown"
    elif session.get("user_id") == "owner-jay":
        actor = "Jay"
    else:
        actor = "System"
    entry = {
        "id": str(uuid.uuid4()),
        "ts": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "description": description,
        "actor": actor,
        "meta": meta or {}
    }
    try:
        with file_lock(ACTIVITY_FILE):
            with open(ACTIVITY_FILE, "a") as f:
                f.write(json.dumps(entry) + "\n")
    except Exception:
        pass

def load_activity(limit=50):
    """Load the most recent activity entries."""
    if not os.path.exists(ACTIVITY_FILE):
        return []
    entries = []
    try:
        with file_lock(ACTIVITY_FILE):
            with open(ACTIVITY_FILE) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            entries.append(json.loads(line))
                        except Exception:
                            pass
    except Exception:
        pass
    entries.sort(key=lambda x: x.get("ts", ""), reverse=True)
    return entries[:limit]
WA_TAX_RATE  = 0.102  # Washington state sales tax
MASTER_PASSWORD = os.getenv("MASTER_PASSWORD", os.getenv("DASHBOARD_PASSWORD", ""))

DEFAULT_SETTINGS = {
    "company": {
        "name": "Pacific Construction",
        "address": "1574 Thornton Ave SW",
        "city": "Pacific", "state": "WA", "zip": "98047",
        "phone": "253.826.2727", "email": "", "website": "",
        "license": "", "bond": "", "tax_rate": 10.2
    },
    "notifications": {
        "lead_email": "",
        "hot_alert": True, "warm_alert": False,
        "weekly_digest": False, "digest_day": "monday", "digest_time": "08:00"
    },
    "billing": {
        "default_terms": "net30",
        "default_notes": "Payment due within 30 days. Thank you for your business.",
        "late_fee_text": ""
    },
    "jobs": {
        "job_types": [
            "Dock Equipment Install", "Mezzanine Fabrication", "Racking System",
            "Structural Install", "Warehouse TI", "Service & Repair",
            "Door Maintenance", "Overhead Door Install", "Commercial Build",
            "Project Management", "Permit Drawings", "Site Plan",
            "Multi-Site Coordination", "Commercial Renovation", "Safety Inspection"
        ],
        "default_status": "quoted",
        "job_prefix": "JOB"
    },
    "dashboard": {
        "default_page": "leads",
        "rows_per_page": 25,
        "auto_refresh": 60,
        "kpi_total": True,
        "kpi_week": True,
        "kpi_hot": True,
        "kpi_warm": True,
        "kpi_cold": True,
        "col_score": True,
        "col_company": True,
        "col_contact": True,
        "col_project": True,
        "col_source": True,
        "col_date": True
    },
    "followup": {
        "enabled": True,
        "steps": [
            {
                "step": 1, "day_offset": 0, "label": "Quote Confirmation",
                "subject": "Your quote from {company_name} — {job_number}",
                "body": "Hi {client_name},\n\nThank you for considering {company_name} for your project. Your quote for {job_type} has been prepared and we'd love to walk you through it.\n\nIf you have any questions about scope or pricing, don't hesitate to reply here or give us a call at {company_phone}.\n\nWe look forward to the opportunity to work with you.\n\n{owner_name}\n{company_name}\n{company_phone}"
            },
            {
                "step": 2, "day_offset": 3, "label": "Check-In",
                "subject": "Quick check-in — {job_number}",
                "body": "Hi {client_name},\n\nJust checking in to make sure the quote landed okay and to see if you have any questions.\n\nWe're happy to adjust scope, break down pricing, or schedule a quick call to go over anything.\n\n{owner_name}\n{company_name}\n{company_phone}"
            },
            {
                "step": 3, "day_offset": 7, "label": "Value Touch",
                "subject": "A few things that set us apart — {company_name}",
                "body": "Hi {client_name},\n\nI wanted to share a bit about how we work. At {company_name} we specialize in {job_type} and have completed projects across the Pacific Northwest for warehouse, industrial, and commercial clients.\n\nOur team handles everything from permitting to final install — you won't be managing multiple contractors.\n\nStill happy to answer any questions on your quote.\n\n{owner_name}\n{company_name}\n{company_phone}"
            },
            {
                "step": 4, "day_offset": 14, "label": "Urgency / CTA",
                "subject": "We have availability opening up — {job_number}",
                "body": "Hi {client_name},\n\nOur schedule is filling up for the coming weeks. If you're still interested in moving forward, now would be a great time to confirm so we can hold your slot.\n\nJust reply here or call us — takes 5 minutes to get on the schedule.\n\n{owner_name}\n{company_name}\n{company_phone}"
            },
            {
                "step": 5, "day_offset": 21, "label": "Break-Up",
                "subject": "Should I close this out? — {job_number}",
                "body": "Hi {client_name},\n\nI haven't heard back and I don't want to keep sending emails if the timing isn't right.\n\nShould I close this quote out for now, or would you like me to circle back in a few weeks?\n\nEither way — no pressure. Just let me know.\n\n{owner_name}\n{company_name}\n{company_phone}"
            }
        ]
    },
    "lead_nurture": {
        "enabled": True,
        "auto_start": True,
        "steps": [
            {
                "step": 1, "day_offset": 2, "label": "Check-In",
                "subject": "Following up on your inquiry — Pacific Construction",
                "body": "Hi {lead_name},\n\nI wanted to follow up on your recent inquiry with Pacific Construction. Our team specializes in warehouse installations, pallet racking, dock equipment, mezzanines, and tenant improvements throughout the Pacific Northwest.\n\nDo you have a few minutes this week for a quick call or site visit? We'd love to learn more about your project and put together a no-obligation estimate.\n\nJust reply here or give us a call at {company_phone}.\n\n{owner_name}\n{company_name}\n{company_phone}"
            },
            {
                "step": 2, "day_offset": 5, "label": "Value Touch",
                "subject": "What sets Pacific Construction apart",
                "body": "Hi {lead_name},\n\nI wanted to share a bit about how we work at Pacific Construction.\n\nWe handle everything in-house — design, permitting, installation, and final inspection. That means one point of contact, no subcontractor surprises, and projects that finish on time.\n\nWe've completed hundreds of installations across Washington for distribution centers, manufacturing facilities, and commercial warehouses.\n\nIf your project is still in planning, we're happy to answer questions at no cost. Would a quick call work?\n\n{owner_name}\n{company_name}\n{company_phone}"
            },
            {
                "step": 3, "day_offset": 10, "label": "Site Visit Ask",
                "subject": "Ready to schedule a quick site visit? — {lead_company}",
                "body": "Hi {lead_name},\n\nA 30-minute site visit is usually all it takes for us to put together an accurate proposal for your project.\n\nThere's no cost or obligation — we just want to make sure we give you a precise number rather than a rough estimate.\n\nWould any time this week or next work for you? You can also reach us directly at {company_phone} to find a time.\n\n{owner_name}\n{company_name}\n{company_phone}"
            },
            {
                "step": 4, "day_offset": 18, "label": "Urgency",
                "subject": "We have schedule availability coming up — Pacific Construction",
                "body": "Hi {lead_name},\n\nOur installation schedule fills up quickly and we have a few slots opening up in the coming weeks.\n\nIf you're still evaluating your project, now would be a great time to get on our calendar so we can hold your spot.\n\nJust reply here or call {company_phone} — it takes about 5 minutes to get scheduled.\n\n{owner_name}\n{company_name}\n{company_phone}"
            },
            {
                "step": 5, "day_offset": 28, "label": "Break-Up",
                "subject": "Should I close this out? — Pacific Construction",
                "body": "Hi {lead_name},\n\nI don't want to keep filling your inbox if the timing isn't right.\n\nShould I close out this inquiry for now? If your project moves forward in the future, we'd love to hear from you — just reach out anytime.\n\nWishing you the best.\n\n{owner_name}\n{company_name}\n{company_phone}"
            }
        ]
    }
}


def load_config():
    if os.path.exists(CONFIG_FILE):
        with file_lock(CONFIG_FILE):
            with open(CONFIG_FILE) as f:
                return json.load(f)
    return {"comp_pin": "1234", "comp_pin_changed": ""}


def save_config(data):
    with file_lock(CONFIG_FILE):
        with open(CONFIG_FILE, "w") as f:
            json.dump(data, f, indent=2)


def load_jobs():
    if os.path.exists(JOBS_FILE):
        with file_lock(JOBS_FILE):
            with open(JOBS_FILE) as f:
                return json.load(f)
    return []


def save_jobs(data):
    with file_lock(JOBS_FILE):
        with open(JOBS_FILE, "w") as f:
            json.dump(data, f, indent=2, default=str)


def load_invoices():
    if os.path.exists(INVOICES_FILE):
        with file_lock(INVOICES_FILE):
            with open(INVOICES_FILE) as f:
                return json.load(f)
    return []


def save_invoices(data):
    with file_lock(INVOICES_FILE):
        with open(INVOICES_FILE, "w") as f:
            json.dump(data, f, indent=2, default=str)


def load_people():
    if os.path.exists(PEOPLE_FILE):
        with file_lock(PEOPLE_FILE):
            with open(PEOPLE_FILE) as f:
                return json.load(f)
    return []


def save_people(data):
    with file_lock(PEOPLE_FILE):
        with open(PEOPLE_FILE, "w") as f:
            json.dump(data, f, indent=2, default=str)


PAYROLL_FILE = "payroll.json"

def load_payroll():
    if os.path.exists(PAYROLL_FILE):
        with file_lock(PAYROLL_FILE):
            with open(PAYROLL_FILE) as f:
                return json.load(f)
    return []

def save_payroll(data):
    with file_lock(PAYROLL_FILE):
        with open(PAYROLL_FILE, "w") as f:
            json.dump(data, f, indent=2, default=str)


def next_invoice_number():
    invoices = load_invoices()
    year = datetime.now().year
    nums = [int(i.get("invoice_number", "0").split("-")[-1]) for i in invoices
            if str(year) in i.get("invoice_number", "")]
    return f"{year}-{str(max(nums) + 1 if nums else 1).zfill(3)}"


def next_job_number():
    jobs = load_jobs()
    year = datetime.now().year
    nums = [int(j.get("job_number", "0").split("-")[-1]) for j in jobs
            if str(year) in j.get("job_number", "")]
    return f"JOB-{year}-{str(max(nums) + 1 if nums else 1).zfill(3)}"


FOLLOWUPS_FILE    = "followups.json"
LEAD_META_FILE    = "lead_meta.json"
LEAD_NURTURES_FILE = "lead_nurtures.json"
LEAD_COMMS_FILE   = "lead_comms.json"
JOB_COMMS_FILE    = "job_comms.json"


# ── Job Costs ──────────────────────────────────────────────────────────────────
def load_jobcosts():
    if os.path.exists(JOBCOSTS_FILE):
        with file_lock(JOBCOSTS_FILE):
            with open(JOBCOSTS_FILE) as f:
                return json.load(f)
    return []

def save_jobcosts(data):
    with file_lock(JOBCOSTS_FILE):
        with open(JOBCOSTS_FILE, "w") as f:
            json.dump(data, f, indent=2)

@app.route("/dashboard/api/jobcosts", methods=["GET"])
@require_auth
def get_jobcosts():
    costs = load_jobcosts()
    costs.sort(key=lambda x: x.get("date", ""), reverse=True)
    return jsonify(costs)

@app.route("/dashboard/api/jobcosts", methods=["POST"])
@require_auth
def create_jobcost():
    data = request.get_json() or {}
    costs = load_jobcosts()
    cost = {
        "cost_id":      str(uuid.uuid4()),
        "job_id":       data.get("job_id", ""),
        "job_number":   data.get("job_number", ""),
        "client_name":  data.get("client_name", ""),
        "vendor":       data.get("vendor", ""),
        "description":  data.get("description", ""),
        "category":     data.get("category", "Materials"),
        "amount":       round(float(data.get("amount", 0)), 2),
        "date":         data.get("date", datetime.now().strftime("%Y-%m-%d")),
        "status":       data.get("status", "pending"),
        "invoice_ref":  data.get("invoice_ref", ""),
        "notes":        data.get("notes", ""),
        "created_at":   datetime.now(timezone.utc).isoformat(),
    }
    costs.append(cost)
    save_jobcosts(costs)
    return jsonify(cost), 201

@app.route("/dashboard/api/jobcosts/<cost_id>", methods=["PUT"])
@require_auth
def update_jobcost(cost_id):
    data = request.get_json() or {}
    costs = load_jobcosts()
    for i, c in enumerate(costs):
        if c["cost_id"] == cost_id:
            if "amount" in data:
                data["amount"] = round(float(data["amount"]), 2)
            costs[i].update({k: v for k, v in data.items() if k != "cost_id"})
            save_jobcosts(costs)
            return jsonify(costs[i])
    return jsonify({"error": "Not found"}), 404

@app.route("/dashboard/api/jobcosts/<cost_id>", methods=["DELETE"])
@require_auth
def delete_jobcost(cost_id):
    costs = load_jobcosts()
    costs = [c for c in costs if c["cost_id"] != cost_id]
    save_jobcosts(costs)
    return jsonify({"ok": True})


VENDOR_INVOICES_FILE = "vendorinvoices.json"

def load_vendor_invoices():
    if os.path.exists(VENDOR_INVOICES_FILE):
        with file_lock(VENDOR_INVOICES_FILE):
            with open(VENDOR_INVOICES_FILE) as f:
                return json.load(f)
    return []

@app.route("/dashboard/api/vendorinvoices/<cost_id>", methods=["GET"])
@require_auth
def get_vendor_invoice(cost_id):
    invoices = load_vendor_invoices()
    inv = next((i for i in invoices if i["cost_id"] == cost_id), None)
    if not inv:
        return jsonify({"error": "No invoice found"}), 404
    return jsonify(inv)


def load_followups():
    if os.path.exists(FOLLOWUPS_FILE):
        with file_lock(FOLLOWUPS_FILE):
            with open(FOLLOWUPS_FILE) as f:
                return json.load(f)
    return []

def save_followups(data):
    with file_lock(FOLLOWUPS_FILE):
        with open(FOLLOWUPS_FILE, "w") as f:
            json.dump(data, f, indent=2, default=str)


def load_lead_meta():
    if os.path.exists(LEAD_META_FILE):
        with file_lock(LEAD_META_FILE):
            with open(LEAD_META_FILE) as f:
                return json.load(f)
    return {}

def save_lead_meta(data):
    with file_lock(LEAD_META_FILE):
        with open(LEAD_META_FILE, "w") as f:
            json.dump(data, f, indent=2, default=str)

def load_lead_nurtures():
    if os.path.exists(LEAD_NURTURES_FILE):
        with file_lock(LEAD_NURTURES_FILE):
            with open(LEAD_NURTURES_FILE) as f:
                return json.load(f)
    return []

def save_lead_nurtures(data):
    with file_lock(LEAD_NURTURES_FILE):
        with open(LEAD_NURTURES_FILE, "w") as f:
            json.dump(data, f, indent=2, default=str)

def load_lead_comms():
    if os.path.exists(LEAD_COMMS_FILE):
        with file_lock(LEAD_COMMS_FILE):
            with open(LEAD_COMMS_FILE) as f:
                return json.load(f)
    return []

def save_lead_comms(data):
    with file_lock(LEAD_COMMS_FILE):
        with open(LEAD_COMMS_FILE, "w") as f:
            json.dump(data, f, indent=2, default=str)

def load_job_comms():
    if os.path.exists(JOB_COMMS_FILE):
        with file_lock(JOB_COMMS_FILE):
            with open(JOB_COMMS_FILE) as f:
                return json.load(f)
    return []

def save_job_comms(data):
    with file_lock(JOB_COMMS_FILE):
        with open(JOB_COMMS_FILE, "w") as f:
            json.dump(data, f, indent=2, default=str)

def log_job_comm(job_id, comm_type, direction, subject, body, sent_by="system"):
    comms = load_job_comms()
    comms.append({
        "comm_id":   str(uuid.uuid4()),
        "job_id":    job_id,
        "type":      comm_type,
        "direction": direction,
        "subject":   subject,
        "body":      body,
        "sent_by":   sent_by,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    save_job_comms(comms)


def log_lead_comm(lead_id, comm_type, direction, subject, body, sent_by="system"):
    """Append a communication record for a lead."""
    comms = load_lead_comms()
    comms.append({
        "comm_id":   str(uuid.uuid4()),
        "lead_id":   lead_id,
        "type":      comm_type,   # email | call | note
        "direction": direction,   # outbound | inbound | internal
        "subject":   subject,
        "body":      body,
        "sent_by":   sent_by,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    save_lead_comms(comms)


def _lead_nurture_cfg():
    cfg = load_config()
    defaults = DEFAULT_SETTINGS["lead_nurture"]
    merged = {**defaults, **{k: v for k, v in cfg.get("lead_nurture", {}).items() if k != "steps"}}
    merged["steps"] = cfg.get("lead_nurture", {}).get("steps", defaults["steps"])
    return merged


def _render_lead_template(text, lead, company):
    name = lead.get("name") or "there"
    first = name.split()[0]
    return (text
        .replace("{lead_name}",    first)
        .replace("{lead_company}", lead.get("company") or "your company")
        .replace("{lead_project}", lead.get("project_details") or "your project")
        .replace("{company_name}", company.get("name", "Pacific Construction"))
        .replace("{company_phone}", company.get("phone", "253.826.2727"))
        .replace("{owner_name}",   company.get("owner_name", "The Pacific Construction Team"))
    )


def _send_lead_nurture_step(lead, step_cfg, nurture_record):
    """Send one lead nurture email step via Gmail SMTP."""
    sender = _integ_val("GMAIL_SENDER")
    pw     = _integ_val("GMAIL_APP_PASSWORD")
    if not sender or not pw:
        print("Lead nurture: Gmail not configured, skipping")
        return False
    email, _ = extract_email_phone(lead.get("contact", ""))
    email = lead.get("email") or email
    if not email:
        print(f"Lead nurture: no email for lead {lead.get('lead_id')}")
        return False

    cfg     = load_config()
    company = cfg.get("company", {})
    subject = _render_lead_template(step_cfg.get("subject", "Following up"), lead, company)
    body    = _render_lead_template(step_cfg.get("body", ""), lead, company)

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = f"{company.get('name','Pacific Construction')} <{sender}>"
        msg["To"]      = email

        html_body = body.replace("\n", "<br>")
        html = f"""<html><body style="font-family:Arial,sans-serif;color:#222;max-width:600px;margin:auto;">
<div style="background:#1a3a5c;padding:24px 32px;">
  <h2 style="color:#fff;margin:0;">{company.get('name','Pacific Construction')}</h2>
  <p style="color:#a8c4e0;margin:4px 0 0;">Warehouse Installation Specialists</p>
</div>
<div style="padding:32px;">{html_body}</div>
<div style="background:#f4f4f4;padding:12px 32px;font-size:12px;color:#999;">
  {company.get('name','Pacific Construction')} &middot; {company.get('address','1574 Thornton Ave SW, Pacific, WA 98047')} &middot; {company.get('phone','253.826.2727')}
</div>
</body></html>"""

        msg.attach(MIMEText(body, "plain"))
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, pw)
            server.sendmail(sender, email, msg.as_string())

        print(f"Lead nurture step {step_cfg['step']} sent to {email}")
        log_lead_comm(lead["lead_id"], "email", "outbound",
                      f"[Auto] {subject}", body, sent_by="sequence")
        return True
    except Exception as e:
        print(f"Lead nurture send failed: {e}")
        return False


def start_lead_nurture_sequence(lead):
    """Start a nurture sequence for a lead. Idempotent."""
    email, _ = extract_email_phone(lead.get("contact", ""))
    email = lead.get("email") or email
    if not email:
        return None
    ncfg = _lead_nurture_cfg()
    if not ncfg.get("enabled") or not ncfg.get("auto_start", True):
        return None
    nurtures = load_lead_nurtures()
    # Don't double-start
    existing = [n for n in nurtures if n["lead_id"] == lead["lead_id"] and n["status"] == "active"]
    if existing:
        return existing[0]
    steps = ncfg.get("steps", [])
    if not steps:
        return None
    today = date.today().isoformat()
    record = {
        "nurture_id":    str(uuid.uuid4()),
        "lead_id":       lead["lead_id"],
        "lead_name":     lead.get("name", ""),
        "lead_email":    email,
        "status":        "active",
        "current_step":  1,
        "started_at":    datetime.now(timezone.utc).isoformat(),
        "stopped_at":    None,
        "stopped_reason": None,
        "steps": [
            {
                "step":            s["step"],
                "label":           s.get("label", f"Step {s['step']}"),
                "scheduled_date":  (date.fromisoformat(today) + timedelta(days=s["day_offset"])).isoformat(),
                "sent_at":         None,
                "status":          "pending"
            }
            for s in steps
        ]
    }
    nurtures.append(record)
    save_lead_nurtures(nurtures)
    return record


def stop_lead_nurture_sequence(lead_id, reason="manual"):
    nurtures = load_lead_nurtures()
    changed = False
    for n in nurtures:
        if n["lead_id"] == lead_id and n["status"] == "active":
            n["status"]         = "stopped"
            n["stopped_reason"] = reason
            n["stopped_at"]     = datetime.now(timezone.utc).isoformat()
            changed = True
    if changed:
        save_lead_nurtures(nurtures)


def process_due_lead_nurtures():
    """Check and send any overdue lead nurture steps."""
    ncfg  = _lead_nurture_cfg()
    steps = {s["step"]: s for s in ncfg.get("steps", [])}
    if not steps:
        return
    nurtures = load_lead_nurtures()
    meta     = load_lead_meta()
    # Build lead lookup
    leads_raw = load_leads()
    lead_map = {l["lead_id"]: l for l in leads_raw}
    today = date.today().isoformat()
    changed = False
    for record in nurtures:
        if record["status"] != "active":
            continue
        lead = lead_map.get(record["lead_id"])
        if not lead:
            continue
        lead_status = meta.get(record["lead_id"], {}).get("status", "new")
        # Auto-stop if lead converted or lost
        if lead_status in ("converted", "lost"):
            record["status"]         = "stopped"
            record["stopped_reason"] = f"lead_{lead_status}"
            record["stopped_at"]     = datetime.now(timezone.utc).isoformat()
            changed = True
            continue
        all_done = True
        for step_rec in record["steps"]:
            if step_rec["status"] == "pending":
                all_done = False
                if step_rec["scheduled_date"] <= today:
                    step_cfg = steps.get(step_rec["step"])
                    if step_cfg:
                        ok = _send_lead_nurture_step(lead, step_cfg, record)
                        step_rec["sent_at"] = datetime.now(timezone.utc).isoformat() if ok else None
                        step_rec["status"]  = "sent" if ok else "failed"
                        record["current_step"] = step_rec["step"] + 1
                        changed = True
        if all_done:
            record["status"] = "completed"
            changed = True
    if changed:
        save_lead_nurtures(nurtures)


def _followup_cfg():
    cfg = load_config()
    defaults = DEFAULT_SETTINGS["followup"]
    merged = {**defaults, **{k: v for k, v in cfg.get("followup", {}).items() if k != "steps"}}
    merged["steps"] = cfg.get("followup", {}).get("steps", defaults["steps"])
    return merged

def _render_template(text, job, owner_name, company):
    first_name = (job.get("client_name") or "").split()[0] or job.get("client_name") or "there"
    return (text
        .replace("{client_name}", first_name)
        .replace("{job_number}", job.get("job_number", ""))
        .replace("{job_type}", job.get("job_type", "your project"))
        .replace("{address}", job.get("address", ""))
        .replace("{company_name}", company.get("name", "Pacific Construction"))
        .replace("{company_phone}", company.get("phone", ""))
        .replace("{owner_name}", owner_name)
    )

def _send_followup_step(job, step_cfg, followup_record):
    """Send one follow-up email step via Gmail SMTP."""
    sender  = _integ_val("GMAIL_SENDER")
    pw      = _integ_val("GMAIL_APP_PASSWORD")
    if not sender or not pw:
        print("Follow-up: Gmail not configured, skipping send")
        return False
    to_email = job.get("client_email", "")
    if not to_email:
        print(f"Follow-up: no client email for job {job.get('job_number')}")
        return False

    cfg     = load_config()
    company = {**DEFAULT_SETTINGS["company"], **cfg.get("company", {})}
    users   = load_users()
    owner   = next((u for u in users if u.get("role") == "owner"), None)
    owner_name = owner.get("display_name", company.get("name", "Pacific Construction")) if owner else company.get("name", "Pacific Construction")

    subject = _render_template(step_cfg["subject"], job, owner_name, company)
    body    = _render_template(step_cfg["body"],    job, owner_name, company)

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = f"{company.get('name','Pacific Construction')} <{sender}>"
        msg["To"]      = to_email

        plain = body
        html  = f"""<!DOCTYPE html><html><body style="font-family:sans-serif;color:#333;max-width:600px;margin:0 auto;padding:24px;">
<div style="white-space:pre-line;font-size:14px;line-height:1.7;">{body}</div>
<hr style="border:none;border-top:1px solid #eee;margin:24px 0;">
<div style="font-size:11px;color:#999;">{company.get('name','')} · {company.get('address','')} · {company.get('city','')} {company.get('state','')} {company.get('zip','')} · {company.get('phone','')}</div>
</body></html>"""

        msg.attach(MIMEText(plain, "plain"))
        msg.attach(MIMEText(html,  "html"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, pw)
            server.sendmail(sender, to_email, msg.as_string())
        print(f"Follow-up step {step_cfg['step']} sent to {to_email} for {job.get('job_number')}")
        return True
    except Exception as e:
        print(f"Follow-up send failed: {e}")
        return False

def start_followup_sequence(job):
    """Start a new follow-up sequence for a quoted job. Idempotent."""
    if not job.get("client_email"):
        return None
    fcfg = _followup_cfg()
    if not fcfg.get("enabled"):
        return None

    followups = load_followups()
    # Stop any existing active sequence for this job
    for f in followups:
        if f["job_id"] == job["job_id"] and f["status"] == "active":
            f["status"] = "stopped"
            f["stopped_reason"] = "restarted"
            f["stopped_at"] = datetime.now(timezone.utc).isoformat()

    today = date.today()
    steps = fcfg["steps"]
    record = {
        "followup_id":   str(uuid.uuid4()),
        "job_id":        job["job_id"],
        "job_number":    job.get("job_number", ""),
        "client_name":   job.get("client_name", ""),
        "client_email":  job.get("client_email", ""),
        "job_type":      job.get("job_type", ""),
        "started_at":    datetime.now(timezone.utc).isoformat(),
        "status":        "active",
        "current_step":  1,
        "total_steps":   len(steps),
        "steps": [
            {
                "step":           s["step"],
                "label":          s.get("label", f"Step {s['step']}"),
                "scheduled_date": (today + timedelta(days=s["day_offset"])).isoformat(),
                "sent_at":        None,
                "status":         "pending"
            }
            for s in steps
        ],
        "stopped_reason": None,
        "stopped_at":     None,
    }
    followups.append(record)
    save_followups(followups)

    # Send step 1 immediately (day_offset=0)
    _process_followup_record(record, job, steps)
    save_followups(load_followups())  # re-save after send update
    return record

def stop_followup_sequence(job_id, reason="manual"):
    followups = load_followups()
    changed = False
    for f in followups:
        if f["job_id"] == job_id and f["status"] == "active":
            f["status"] = "stopped"
            f["stopped_reason"] = reason
            f["stopped_at"] = datetime.now(timezone.utc).isoformat()
            changed = True
    if changed:
        save_followups(followups)

def _process_followup_record(record, job, steps):
    """Check and send any due steps for a single record. Mutates record in place."""
    if record["status"] != "active":
        return
    today = date.today().isoformat()
    all_done = True
    for step_rec in record["steps"]:
        if step_rec["status"] == "pending":
            all_done = False
            if step_rec["scheduled_date"] <= today:
                step_cfg = next((s for s in steps if s["step"] == step_rec["step"]), None)
                if step_cfg:
                    ok = _send_followup_step(job, step_cfg, record)
                    step_rec["sent_at"] = datetime.now(timezone.utc).isoformat() if ok else None
                    step_rec["status"]  = "sent" if ok else "failed"
                    record["current_step"] = step_rec["step"] + 1
    if all_done:
        record["status"] = "completed"

def process_due_followups():
    """Called hourly by background thread and manually via API."""
    followups = load_followups()
    if not followups:
        return
    fcfg  = _followup_cfg()
    steps = fcfg["steps"]
    jobs  = load_jobs()
    job_map = {j["job_id"]: j for j in jobs}
    changed = False
    for record in followups:
        if record["status"] != "active":
            continue
        job = job_map.get(record["job_id"])
        if not job:
            continue
        # Auto-stop if job status changed from quoted
        if job.get("status") != "quoted":
            record["status"]        = "stopped"
            record["stopped_reason"] = "job_status_changed"
            record["stopped_at"]    = datetime.now(timezone.utc).isoformat()
            changed = True
            continue
        before = str(record["steps"])
        _process_followup_record(record, job, steps)
        if str(record["steps"]) != before:
            changed = True
    if changed:
        save_followups(followups)

def _start_followup_scheduler():
    """Background thread that runs follow-up and lead nurture processors every hour."""
    def _loop():
        import time
        while True:
            time.sleep(3600)
            try:
                process_due_followups()
            except Exception as e:
                print(f"Follow-up scheduler error: {e}")
            try:
                process_due_lead_nurtures()
            except Exception as e:
                print(f"Lead nurture scheduler error: {e}")
    t = threading.Thread(target=_loop, daemon=True)
    t.start()


# ── Job routes ──

@app.route("/dashboard/api/jobs", methods=["GET"])
@require_auth
def get_jobs():
    jobs = load_jobs()
    jobs.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return jsonify(jobs)


@app.route("/dashboard/api/jobs", methods=["POST"])
@require_auth
def create_job():
    data = request.get_json() or {}
    jobs = load_jobs()
    job = {
        "job_id": str(uuid.uuid4()),
        "job_number": next_job_number(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": data.get("status", "quoted"),
        "client_name": data.get("client_name", ""),
        "client_company": data.get("client_company", ""),
        "client_email": data.get("client_email", ""),
        "client_phone": data.get("client_phone", ""),
        "address": data.get("address", ""),
        "description": data.get("description", ""),
        "job_type": data.get("job_type", ""),
        "value": float(data.get("value") or 0),
        "start_date": data.get("start_date", ""),
        "end_date": data.get("end_date", ""),
        "workers": data.get("workers", ""),
        "subcontractors": data.get("subcontractors", ""),
        "notes": data.get("notes", ""),
        "lead_id": data.get("lead_id", ""),
    }
    jobs.append(job)
    save_jobs(jobs)
    log_activity("job_created", f"New job created for {job['client_name']} — {job.get('job_type','') or job.get('description','')[:40]}", {"job_id": job["job_id"], "client": job["client_name"], "status": job["status"]})
    if job.get("status") == "quoted" and job.get("client_email"):
        threading.Thread(target=start_followup_sequence, args=(job,), daemon=True).start()
    # If created from a lead, mark lead as converted and stop nurture
    if job.get("lead_id"):
        def _convert_lead(lead_id):
            meta = load_lead_meta()
            if lead_id not in meta:
                meta[lead_id] = {}
            meta[lead_id]["status"] = "converted"
            meta[lead_id]["converted_job_id"] = job["job_id"]
            meta[lead_id]["converted_at"] = datetime.now(timezone.utc).isoformat()
            save_lead_meta(meta)
            stop_lead_nurture_sequence(lead_id, "converted_to_job")
        threading.Thread(target=_convert_lead, args=(job["lead_id"],), daemon=True).start()
    return jsonify(job), 201


@app.route("/dashboard/api/jobs/<job_id>", methods=["PUT"])
@require_auth
def update_job(job_id):
    data = request.get_json() or {}
    jobs = load_jobs()
    for i, j in enumerate(jobs):
        if j["job_id"] == job_id:
            prev_status = j.get("status")
            jobs[i].update({k: v for k, v in data.items() if k != "job_id"})
            save_jobs(jobs)
            updated = jobs[i]
            new_status = updated.get("status")
            if new_status != prev_status:
                log_activity("job_updated", f"Job status changed to {new_status} — {updated.get('client_name','')} ({updated.get('job_type','')})", {"job_id": job_id, "status": new_status, "client": updated.get("client_name","")})
            if updated.get("status") == "quoted" and updated.get("client_email"):
                # only start if not already active
                existing = [f for f in load_followups() if f["job_id"] == job_id and f["status"] == "active"]
                if not existing:
                    threading.Thread(target=start_followup_sequence, args=(updated,), daemon=True).start()
            elif updated.get("status") != "quoted":
                threading.Thread(target=stop_followup_sequence, args=(job_id, "job_status_changed"), daemon=True).start()
            return jsonify(jobs[i])
    return jsonify({"error": "Not found"}), 404


@app.route("/dashboard/api/jobs/<job_id>", methods=["DELETE"])
@require_auth
def delete_job(job_id):
    jobs = load_jobs()
    deleted = next((j for j in jobs if j["job_id"] == job_id), None)
    jobs = [j for j in jobs if j["job_id"] != job_id]
    save_jobs(jobs)
    if deleted:
        log_activity("job_deleted", f"Job deleted — {deleted.get('client_name','')} ({deleted.get('job_type','')})", {"job_id": job_id})
    return jsonify({"ok": True})


# ── Follow-up sequence routes ──────────────────────────────────────────────────

@app.route("/dashboard/api/followups", methods=["GET"])
@require_auth
def list_followups():
    process_due_followups()
    followups = load_followups()
    # Enrich with current job status
    jobs = load_jobs()
    job_map = {j["job_id"]: j for j in jobs}
    result = []
    for f in followups:
        item = dict(f)
        job = job_map.get(f["job_id"], {})
        item["job_status"] = job.get("status", "")
        item["client_company"] = job.get("client_company", "")
        result.append(item)
    result.sort(key=lambda x: x.get("started_at", ""), reverse=True)
    return jsonify(result)


@app.route("/dashboard/api/followups/start", methods=["POST"])
@require_auth
def api_start_followup():
    data = request.json or {}
    job_id = data.get("job_id")
    jobs = load_jobs()
    job = next((j for j in jobs if j["job_id"] == job_id), None)
    if not job:
        return jsonify({"ok": False, "error": "Job not found"}), 404
    if not job.get("client_email"):
        return jsonify({"ok": False, "error": "Job has no client email address"}), 400
    record = start_followup_sequence(job)
    if not record:
        return jsonify({"ok": False, "error": "Follow-ups disabled or no email configured"}), 400
    return jsonify({"ok": True, "followup": record})


@app.route("/dashboard/api/followups/<followup_id>/pause", methods=["POST"])
@require_auth
def pause_followup(followup_id):
    followups = load_followups()
    for f in followups:
        if f["followup_id"] == followup_id and f["status"] == "active":
            f["status"] = "paused"
            save_followups(followups)
            return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "Not found or not active"}), 404


@app.route("/dashboard/api/followups/<followup_id>/resume", methods=["POST"])
@require_auth
def resume_followup(followup_id):
    followups = load_followups()
    for f in followups:
        if f["followup_id"] == followup_id and f["status"] == "paused":
            f["status"] = "active"
            save_followups(followups)
            return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "Not found or not paused"}), 404


@app.route("/dashboard/api/followups/<followup_id>/stop", methods=["POST"])
@require_auth
def api_stop_followup(followup_id):
    followups = load_followups()
    for f in followups:
        if f["followup_id"] == followup_id:
            f["status"] = "stopped"
            f["stopped_reason"] = "manual"
            f["stopped_at"] = datetime.now(timezone.utc).isoformat()
            save_followups(followups)
            return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "Not found"}), 404


@app.route("/dashboard/api/followups/process", methods=["POST"])
@require_auth
def api_process_followups():
    process_due_followups()
    return jsonify({"ok": True})


@app.route("/dashboard/api/followups/send-test", methods=["POST"])
@require_auth
def send_test_followup():
    data     = request.json or {}
    to_email = data.get("to_email", "").strip()
    subject  = data.get("subject", "Test Email")
    body_txt = data.get("body", "")
    step     = data.get("step", 1)
    label    = data.get("label", f"Step {step}")

    if not to_email:
        return jsonify({"ok": False, "error": "No recipient email"}), 400

    sender = _integ_val("GMAIL_SENDER")
    pw     = _integ_val("GMAIL_APP_PASSWORD")
    if not sender or not pw:
        return jsonify({"ok": False, "error": "Gmail not configured — set credentials in Settings → Integrations"}), 400

    cfg        = load_config()
    company    = {**DEFAULT_SETTINGS["company"], **cfg.get("company", {})}
    users      = load_users()
    owner      = next((u for u in users if u.get("role") == "owner"), None)
    owner_name = owner.get("display_name", company["name"]) if owner else company["name"]

    sample_job = {
        "job_number": "JOB-2026-042",
        "job_type":   "Mezzanine Fabrication",
        "address":    "Kent, WA",
        "client_name": "John Smith",
        "client_email": to_email,
    }
    rendered_subject = _render_template(subject,  sample_job, owner_name, company)
    rendered_body    = _render_template(body_txt, sample_job, owner_name, company)

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[TEST — {label}] {rendered_subject}"
        msg["From"]    = f"{company['name']} <{sender}>"
        msg["To"]      = to_email

        plain = f"--- TEST EMAIL (Step {step}: {label}) ---\n\n{rendered_body}"
        html  = f"""<!DOCTYPE html><html><body style="font-family:sans-serif;color:#333;max-width:600px;margin:0 auto;padding:24px;">
<div style="background:#fff3cd;border:1px solid #ffc107;border-radius:6px;padding:10px 14px;margin-bottom:20px;font-size:12px;color:#856404;">
  <strong>TEST EMAIL</strong> — Step {step}: {label}. Sample data used in place of real job values.
</div>
<div style="white-space:pre-line;font-size:14px;line-height:1.7;">{rendered_body}</div>
<hr style="border:none;border-top:1px solid #eee;margin:24px 0;">
<div style="font-size:11px;color:#999;">{company.get('name','')} &middot; {company.get('address','')} &middot; {company.get('city','')} {company.get('state','')} {company.get('zip','')} &middot; {company.get('phone','')}</div>
</body></html>"""

        msg.attach(MIMEText(plain, "plain"))
        msg.attach(MIMEText(html,  "html"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, pw)
            server.sendmail(sender, to_email, msg.as_string())
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/dashboard/api/lead-nurtures/send-test", methods=["POST"])
@require_auth
def send_test_lead_nurture():
    data     = request.json or {}
    to_email = data.get("to_email", "").strip()
    subject  = data.get("subject", "Test Email")
    body_txt = data.get("body", "")
    step     = data.get("step", 1)
    label    = data.get("label", f"Step {step}")

    if not to_email:
        return jsonify({"ok": False, "error": "No recipient email"}), 400

    sender = _integ_val("GMAIL_SENDER")
    pw     = _integ_val("GMAIL_APP_PASSWORD")
    if not sender or not pw:
        return jsonify({"ok": False, "error": "Gmail not configured — set credentials in Settings → Integrations"}), 400

    cfg     = load_config()
    company = {**DEFAULT_SETTINGS["company"], **cfg.get("company", {})}

    sample_lead = {
        "lead_id": "sample",
        "name":    "Sarah Chen",
        "company": "Pacific Northwest Cold Storage",
        "project_details": "Expand refrigerated warehouse",
        "contact": to_email,
    }
    rendered_subject = _render_lead_template(subject,  sample_lead, company)
    rendered_body    = _render_lead_template(body_txt, sample_lead, company)

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[TEST — {label}] {rendered_subject}"
        msg["From"]    = f"{company['name']} <{sender}>"
        msg["To"]      = to_email

        plain = f"--- TEST EMAIL (Lead Nurture Step {step}: {label}) ---\n\n{rendered_body}"
        html  = f"""<!DOCTYPE html><html><body style="font-family:sans-serif;color:#333;max-width:600px;margin:0 auto;padding:24px;">
<div style="background:#fff3cd;border:1px solid #ffc107;border-radius:6px;padding:10px 14px;margin-bottom:20px;font-size:12px;color:#856404;">
  <strong>TEST EMAIL</strong> — Lead Nurture Step {step}: {label}. Sample data used.
</div>
<div style="white-space:pre-line;font-size:14px;line-height:1.7;">{rendered_body}</div>
<hr style="border:none;border-top:1px solid #eee;margin:24px 0;">
<div style="font-size:11px;color:#999;">{company.get('name','')} &middot; {company.get('address','')} &middot; {company.get('city','')} {company.get('state','')} &middot; {company.get('phone','')}</div>
</body></html>"""
        msg.attach(MIMEText(plain, "plain"))
        msg.attach(MIMEText(html,  "html"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, pw)
            server.sendmail(sender, to_email, msg.as_string())
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/dashboard/api/jobs/<job_id>/followup", methods=["GET"])
@require_auth
def get_job_followup(job_id):
    process_due_followups()
    followups = load_followups()
    active = next((f for f in reversed(followups) if f["job_id"] == job_id and f["status"] in ("active","paused")), None)
    if not active:
        active = next((f for f in reversed(followups) if f["job_id"] == job_id), None)
    return jsonify(active or {})


@app.route("/dashboard/api/jobs/<job_id>/files", methods=["GET"])
def list_job_files(job_id):
    folder = os.path.join("job_files", job_id)
    if not os.path.exists(folder):
        return jsonify([])
    files = []
    for fname in sorted(os.listdir(folder)):
        # Skip thumbnail files — they're shown inline, not as separate entries
        if fname.endswith(".thumb.png"):
            continue
        fpath = os.path.join(folder, fname)
        stat = os.stat(fpath)
        ext = fname.rsplit(".", 1)[-1].lower() if "." in fname else ""
        thumb_fname = fname + ".thumb.png"
        thumb_path = os.path.join(folder, thumb_fname)
        thumb_url = f"/dashboard/job-files/{job_id}/{thumb_fname}" if os.path.exists(thumb_path) else None
        files.append({
            "name": fname,
            "size": stat.st_size,
            "ext": ext,
            "is_image": ext in ("jpg","jpeg","png","gif","webp","bmp"),
            "url": f"/dashboard/job-files/{job_id}/{fname}",
            "thumbnail_url": thumb_url,
            "uploaded": datetime.fromtimestamp(stat.st_mtime).strftime("%b %d, %Y"),
        })
    return jsonify(files)


@app.route("/dashboard/api/jobs/<job_id>/files", methods=["POST"])
@require_auth
def upload_job_file(job_id):
    if "file" not in request.files:
        return jsonify({"error": "No file"}), 400
    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "Empty filename"}), 400
    folder = os.path.join("job_files", job_id)
    os.makedirs(folder, exist_ok=True)
    # Sanitize filename
    safe = re.sub(r'[^\w\.\-]', '_', f.filename)
    save_path = os.path.join(folder, safe)
    f.save(save_path)
    return jsonify({"ok": True, "name": safe})


@app.route("/dashboard/job-files/<job_id>/<filename>")
def serve_job_file(job_id, filename):
    from flask import send_from_directory
    folder = os.path.abspath(os.path.join("job_files", job_id))
    return send_from_directory(folder, filename)


@app.route("/dashboard/api/jobs/<job_id>/files/<filename>", methods=["DELETE"])
@require_auth
def delete_job_file(job_id, filename):
    safe = re.sub(r'[^\w\.\-]', '_', filename)
    fpath = os.path.join("job_files", job_id, safe)
    if os.path.exists(fpath):
        os.remove(fpath)
    return jsonify({"ok": True})


# ── Invoice routes ──

@app.route("/dashboard/api/activity")
def api_activity():
    return jsonify(load_activity(50))


@app.route("/dashboard/api/invoices", methods=["GET"])
@require_auth
def get_invoices():
    invoices = load_invoices()
    invoices.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return jsonify(invoices)


@app.route("/dashboard/api/invoices", methods=["POST"])
@require_auth
def create_invoice():
    data = request.get_json() or {}
    invoices = load_invoices()
    line_items = data.get("line_items", [])
    subtotal = sum(float(item.get("amount", 0)) for item in line_items)
    apply_tax = data.get("apply_tax", False)
    tax = round(subtotal * WA_TAX_RATE, 2) if apply_tax else 0
    total = round(subtotal + tax, 2)
    invoice = {
        "invoice_id": str(uuid.uuid4()),
        "invoice_number": next_invoice_number(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "date": data.get("date", datetime.now().strftime("%Y-%m-%d")),
        "due_date": data.get("due_date", ""),
        "status": "draft",
        "client_name": data.get("client_name", ""),
        "client_company": data.get("client_company", ""),
        "client_email": data.get("client_email", ""),
        "client_address": data.get("client_address", ""),
        "line_items": line_items,
        "subtotal": round(subtotal, 2),
        "apply_tax": apply_tax,
        "tax_rate": WA_TAX_RATE if apply_tax else 0,
        "tax": tax,
        "total": total,
        "notes": data.get("notes", "Payment due within 30 days. Thank you for your business."),
        "job_id": data.get("job_id", ""),
        "paid_at": None,
    }
    invoices.append(invoice)
    save_invoices(invoices)
    log_activity("invoice_created", f"Invoice {invoice['invoice_number']} created for {invoice['client_name']} — ${total:,.2f}", {"invoice_id": invoice["invoice_id"], "amount": total, "client": invoice["client_name"]})
    return jsonify(invoice), 201


@app.route("/dashboard/api/invoices/<inv_id>", methods=["PUT"])
@require_auth
def update_invoice(inv_id):
    data = request.get_json() or {}
    invoices = load_invoices()
    for i, inv in enumerate(invoices):
        if inv["invoice_id"] == inv_id:
            if "line_items" in data:
                line_items = data["line_items"]
                subtotal = sum(float(item.get("amount", 0)) for item in line_items)
                apply_tax = data.get("apply_tax", inv.get("apply_tax", False))
                tax = round(subtotal * WA_TAX_RATE, 2) if apply_tax else 0
                data["subtotal"] = round(subtotal, 2)
                data["tax"] = tax
                data["total"] = round(subtotal + tax, 2)
                data["tax_rate"] = WA_TAX_RATE if apply_tax else 0
            prev_status = invoices[i].get("status")
            if data.get("status") == "paid" and not invoices[i].get("paid_at"):
                data["paid_at"] = datetime.now(timezone.utc).isoformat()
            invoices[i].update({k: v for k, v in data.items() if k != "invoice_id"})
            save_invoices(invoices)
            new_status = invoices[i].get("status")
            if new_status != prev_status:
                client = invoices[i].get("client_name", "")
                num = invoices[i].get("invoice_number", "")
                total = invoices[i].get("total", 0)
                if new_status == "paid":
                    log_activity("invoice_paid", f"Invoice {num} marked paid — {client} (${total:,.2f})", {"invoice_id": inv_id, "client": client})
                else:
                    log_activity("invoice_updated", f"Invoice {num} status changed to {new_status} — {client}", {"invoice_id": inv_id, "client": client})
            return jsonify(invoices[i])
    return jsonify({"error": "Not found"}), 404


@app.route("/dashboard/api/invoices/<inv_id>", methods=["DELETE"])
@require_auth
def delete_invoice(inv_id):
    invoices = load_invoices()
    deleted = next((i for i in invoices if i["invoice_id"] == inv_id), None)
    invoices = [i for i in invoices if i["invoice_id"] != inv_id]
    save_invoices(invoices)
    if deleted:
        log_activity("invoice_deleted", f"Invoice {deleted.get('invoice_number','')} deleted — {deleted.get('client_name','')}", {"invoice_id": inv_id})
    return jsonify({"ok": True})

@app.route("/dashboard/api/invoices/<inv_id>/send", methods=["POST"])
@require_auth
def send_invoice(inv_id):
    invoices = load_invoices()
    inv = next((i for i in invoices if i["invoice_id"] == inv_id), None)
    if not inv:
        return jsonify({"error": "Not found"}), 404
    data = request.get_json(silent=True) or {}
    email = data.get("to_email") or inv.get("client_email", "")
    subject = data.get("subject") or f"Invoice {inv['invoice_number']} — Pacific Construction"
    custom_note = data.get("message", "")
    if not email:
        return jsonify({"error": "No client email on invoice"}), 400
    try:
        invoice_html = _invoice_html(inv)
        note_block = f'<div style="font-family:sans-serif;font-size:14px;line-height:1.6;color:#333;padding:20px 0 28px;">{custom_note.replace(chr(10),"<br>")}</div>' if custom_note else ""
        html = note_block + invoice_html
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"Pacific Construction <{GMAIL_SENDER}>"
        msg["To"] = email
        msg.attach(MIMEText(html, "html"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_SENDER, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_SENDER, email, msg.as_string())
        # mark as sent
        for i, item in enumerate(invoices):
            if item["invoice_id"] == inv_id:
                invoices[i]["status"] = "sent"
                save_invoices(invoices)
                break
        log_activity("invoice_sent", f"Invoice {inv['invoice_number']} emailed to {email} — {inv.get('client_name','')} (${inv.get('total',0):,.2f})", {"invoice_id": inv_id, "client": inv.get("client_name",""), "email": email})
        # auto-log to job comms if this invoice is linked to a job
        job_id = inv.get("job_id")
        if job_id:
            log_job_comm(
                job_id,
                comm_type="email",
                direction="outbound",
                subject=f"Invoice {inv['invoice_number']} sent to {email}",
                body=f"Invoice {inv.get('invoice_number','')} emailed to {email}.",
                sent_by="system",
            )
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/dashboard/invoice/<inv_id>")
def invoice_preview(inv_id):
    invoices = load_invoices()
    inv = next((i for i in invoices if i["invoice_id"] == inv_id), None)
    if not inv:
        return "Invoice not found", 404
    return _invoice_html(inv)


def _invoice_html(inv):
    items_html = ""
    for item in inv.get("line_items", []):
        qty = item.get("qty", 1)
        rate = float(item.get("rate", 0))
        amount = float(item.get("amount", 0))
        items_html += f"""
        <tr>
          <td style="padding:10px 12px;border-bottom:1px solid #eee;">{item.get('description','')}</td>
          <td style="padding:10px 12px;border-bottom:1px solid #eee;text-align:center;">{qty}</td>
          <td style="padding:10px 12px;border-bottom:1px solid #eee;text-align:right;">${rate:,.2f}</td>
          <td style="padding:10px 12px;border-bottom:1px solid #eee;text-align:right;">${amount:,.2f}</td>
        </tr>"""

    tax_row = ""
    if inv.get("apply_tax") and inv.get("tax", 0) > 0:
        tax_row = f'<tr><td colspan="3" style="padding:6px 12px;text-align:right;color:#666;">WA Sales Tax ({inv["tax_rate"]*100:.1f}%)</td><td style="padding:6px 12px;text-align:right;">${inv["tax"]:,.2f}</td></tr>'

    status_color = {"draft":"#888","sent":"#2563eb","paid":"#16a34a","overdue":"#dc2626"}.get(inv.get("status","draft"),"#888")

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>Invoice {inv.get('invoice_number')}</title>
<style>
  body{{font-family:Arial,sans-serif;color:#222;margin:0;padding:0;background:#f5f5f5;}}
  .page{{max-width:760px;margin:32px auto;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 2px 20px rgba(0,0,0,0.1);}}
  @media print{{body{{background:#fff;}}.page{{margin:0;box-shadow:none;border-radius:0;}} .no-print{{display:none;}}}}
</style>
</head><body>
<div class="page">
  <div style="background:#1a1a1a;padding:28px 36px;display:flex;align-items:center;justify-content:space-between;">
    <div>
      <div style="font-size:22px;font-weight:800;color:#fff;letter-spacing:2px;">PACIFIC CONSTRUCTION</div>
      <div style="font-size:11px;color:#e8650a;letter-spacing:1.5px;margin-top:3px;">WAREHOUSE INSTALLATION SPECIALISTS</div>
    </div>
    <div style="text-align:right;">
      <div style="font-size:28px;font-weight:700;color:#e8650a;">INVOICE</div>
      <div style="color:#aaa;font-size:13px;margin-top:2px;">#{inv.get('invoice_number')}</div>
      <div style="display:inline-block;margin-top:6px;padding:3px 10px;border-radius:4px;font-size:11px;font-weight:700;color:#fff;background:{status_color};">{inv.get('status','draft').upper()}</div>
    </div>
  </div>
  <div style="padding:28px 36px;">
    <div style="display:flex;justify-content:space-between;margin-bottom:28px;">
      <div>
        <div style="font-size:10px;font-weight:700;color:#999;letter-spacing:1px;text-transform:uppercase;margin-bottom:6px;">Bill To</div>
        <div style="font-weight:700;font-size:15px;">{inv.get('client_name','')}</div>
        <div style="color:#555;">{inv.get('client_company','')}</div>
        <div style="color:#555;white-space:pre-line;">{inv.get('client_address','')}</div>
        <div style="color:#555;">{inv.get('client_email','')}</div>
      </div>
      <div style="text-align:right;">
        <div style="font-size:10px;font-weight:700;color:#999;letter-spacing:1px;text-transform:uppercase;margin-bottom:6px;">From</div>
        <div style="font-weight:700;">Pacific Construction</div>
        <div style="color:#555;">1574 Thornton Ave SW</div>
        <div style="color:#555;">Pacific, WA 98047</div>
        <div style="color:#555;">253.826.2727</div>
        <div style="margin-top:12px;">
          <div style="font-size:11px;color:#999;">Invoice Date: <strong>{inv.get('date','')}</strong></div>
          <div style="font-size:11px;color:#999;">Due Date: <strong>{inv.get('due_date','')}</strong></div>
        </div>
      </div>
    </div>
    <table style="width:100%;border-collapse:collapse;margin-bottom:16px;">
      <thead>
        <tr style="background:#f8f8f8;">
          <th style="padding:10px 12px;text-align:left;font-size:11px;color:#666;border-bottom:2px solid #e8650a;">Description</th>
          <th style="padding:10px 12px;text-align:center;font-size:11px;color:#666;border-bottom:2px solid #e8650a;">Qty</th>
          <th style="padding:10px 12px;text-align:right;font-size:11px;color:#666;border-bottom:2px solid #e8650a;">Rate</th>
          <th style="padding:10px 12px;text-align:right;font-size:11px;color:#666;border-bottom:2px solid #e8650a;">Amount</th>
        </tr>
      </thead>
      <tbody>{items_html}</tbody>
      <tfoot>
        <tr><td colspan="3" style="padding:8px 12px;text-align:right;font-weight:600;">Subtotal</td><td style="padding:8px 12px;text-align:right;">${inv.get('subtotal',0):,.2f}</td></tr>
        {tax_row}
        <tr style="background:#1a1a1a;"><td colspan="3" style="padding:12px;text-align:right;font-weight:700;color:#fff;font-size:15px;">TOTAL</td><td style="padding:12px;text-align:right;font-weight:700;color:#e8650a;font-size:18px;">${inv.get('total',0):,.2f}</td></tr>
      </tfoot>
    </table>
    {f'<div style="background:#f9f9f9;border-radius:6px;padding:14px;font-size:13px;color:#555;margin-bottom:16px;"><strong>Notes:</strong> {inv.get("notes","")}</div>' if inv.get("notes") else ""}
    <div style="border-top:2px solid #e8650a;padding-top:14px;text-align:center;font-size:11px;color:#999;">
      Pacific Construction · 1574 Thornton Ave SW, Pacific, WA 98047 · 253.826.2727
    </div>
  </div>
</div>
<div class="no-print" style="text-align:center;padding:16px;">
  <button onclick="window.print()" style="background:#e8650a;color:#fff;border:none;padding:10px 24px;border-radius:6px;font-size:14px;font-weight:700;cursor:pointer;">Print / Save as PDF</button>
</div>
</body></html>"""


@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")


@app.route("/dashboard/api/leads")
def dashboard_leads():
    leads = load_leads()
    meta = load_lead_meta()
    nurtures = load_lead_nurtures()
    nurture_map = {}
    for n in nurtures:
        if n["status"] == "active":
            nurture_map[n["lead_id"]] = n
    for lead in leads:
        lid = lead.get("lead_id", "")
        m = meta.get(lid, {})
        lead["lead_status"] = m.get("status", "new")
        lead["converted_job_id"] = m.get("converted_job_id", "")
        n = nurture_map.get(lid)
        if n:
            steps_sent = sum(1 for s in n["steps"] if s["status"] == "sent")
            next_step  = next((s for s in n["steps"] if s["status"] == "pending"), None)
            lead["nurture"] = {
                "active":       True,
                "steps_sent":   steps_sent,
                "total_steps":  len(n["steps"]),
                "next_date":    next_step["scheduled_date"] if next_step else None,
                "next_label":   next_step["label"] if next_step else None,
                "nurture_id":   n["nurture_id"],
            }
        else:
            lead["nurture"] = {"active": False}
    leads.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return jsonify(leads)


@app.route("/dashboard/api/leads", methods=["POST"])
@require_auth
def create_lead_dashboard():
    data = request.get_json() or {}
    lead = {
        "lead_id":        str(uuid.uuid4()),
        "timestamp":      datetime.now(timezone.utc).isoformat(),
        "name":           data.get("name","").strip(),
        "company":        data.get("company","").strip(),
        "email":          data.get("email","").strip(),
        "contact":        data.get("contact","").strip(),
        "location":       data.get("location","").strip(),
        "project_details":data.get("project_details","").strip(),
        "source":         data.get("source","manual").strip(),
    }
    lead["score"] = score_lead(lead)
    append_lead(lead)
    meta = load_lead_meta()
    meta[lead["lead_id"]] = {"status": "new"}
    save_lead_meta(meta)
    log_activity("lead_created", f"New lead: {lead.get('name','')} from {lead.get('company','') or lead.get('location','')}", {"lead_id": lead["lead_id"], "name": lead.get("name",""), "score": lead.get("score","")})
    return jsonify({"ok": True, "lead_id": lead["lead_id"]})


@app.route("/dashboard/api/leads/<lead_id>", methods=["PUT"])
@require_auth
def update_lead(lead_id):
    data = request.get_json() or {}
    meta = load_lead_meta()
    if lead_id not in meta:
        meta[lead_id] = {}
    allowed = {"status", "notes", "qualified_at", "lost_reason"}
    for k, v in data.items():
        if k in allowed:
            meta[lead_id][k] = v
    new_status = data.get("status")
    if new_status in ("converted", "lost"):
        stop_lead_nurture_sequence(lead_id, f"lead_{new_status}")
    elif new_status == "new" or new_status == "contacted":
        pass  # no sequence action
    save_lead_meta(meta)
    if new_status:
        leads_all = load_leads()
        lead_obj = next((l for l in leads_all if l.get("lead_id") == lead_id), {})
        label = {"new":"New","contacted":"Contacted","qualified":"Qualified","converted":"Converted","lost":"Lost"}.get(new_status, new_status)
        log_activity("lead_status", f"Lead marked {label} — {lead_obj.get('name','Unknown')} ({lead_obj.get('company','')})", {"lead_id": lead_id, "status": new_status})
    return jsonify({"ok": True, "lead_id": lead_id, "status": meta[lead_id].get("status")})


@app.route("/dashboard/api/leads/<lead_id>/send-email", methods=["POST"])
@require_auth
def send_lead_manual_email(lead_id):
    """Send a manual one-off email to a lead and mark them as contacted."""
    data     = request.get_json() or {}
    to_email = data.get("to_email", "").strip()
    subject  = data.get("subject", "").strip()
    body_txt = data.get("body", "").strip()

    if not to_email:
        return jsonify({"ok": False, "error": "No recipient email"}), 400
    if not subject or not body_txt:
        return jsonify({"ok": False, "error": "Subject and body are required"}), 400

    sender = _integ_val("GMAIL_SENDER")
    pw     = _integ_val("GMAIL_APP_PASSWORD")
    if not sender or not pw:
        return jsonify({"ok": False, "error": "Gmail not configured — set credentials in Settings → Integrations"}), 400

    cfg     = load_config()
    company = {**DEFAULT_SETTINGS["company"], **cfg.get("company", {})}

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = f"{company.get('name','Pacific Construction')} <{sender}>"
        msg["To"]      = to_email

        html_body = body_txt.replace("\n", "<br>")
        html = f"""<html><body style="font-family:Arial,sans-serif;color:#222;max-width:600px;margin:auto;">
<div style="background:#1a3a5c;padding:24px 32px;">
  <h2 style="color:#fff;margin:0;">{company.get('name','Pacific Construction')}</h2>
  <p style="color:#a8c4e0;margin:4px 0 0;">Warehouse Installation Specialists</p>
</div>
<div style="padding:32px;font-size:14px;line-height:1.8;">{html_body}</div>
<div style="background:#f4f4f4;padding:12px 32px;font-size:12px;color:#999;">
  {company.get('name','')} &middot; {company.get('address','')} &middot; {company.get('phone','')}
</div>
</body></html>"""

        msg.attach(MIMEText(body_txt, "plain"))
        msg.attach(MIMEText(html, "html"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, pw)
            server.sendmail(sender, to_email, msg.as_string())

        # Mark lead as contacted
        meta = load_lead_meta()
        if lead_id not in meta:
            meta[lead_id] = {}
        if meta[lead_id].get("status", "new") == "new":
            meta[lead_id]["status"] = "contacted"
        meta[lead_id]["last_manual_email"] = datetime.now(timezone.utc).isoformat()
        save_lead_meta(meta)
        # Log the communication
        user = getattr(g, "user", {})
        sent_by = user.get("username", "unknown") if isinstance(user, dict) else "unknown"
        log_lead_comm(lead_id, "email", "outbound", subject, body_txt, sent_by=sent_by)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/dashboard/api/lead-nurtures", methods=["GET"])
@require_auth
def list_lead_nurtures():
    process_due_lead_nurtures()
    nurtures = load_lead_nurtures()
    nurtures.sort(key=lambda x: x.get("started_at", ""), reverse=True)
    return jsonify(nurtures)


@app.route("/dashboard/api/lead-nurtures/start", methods=["POST"])
@require_auth
def api_start_lead_nurture():
    data = request.json or {}
    lead_id = data.get("lead_id")
    # Look up lead
    leads_raw = load_leads()
    lead = next((l for l in leads_raw if l.get("lead_id") == lead_id), None)
    if not lead:
        return jsonify({"ok": False, "error": "Lead not found"}), 404
    email, _ = extract_email_phone(lead.get("contact", ""))
    email = lead.get("email") or email
    if not email:
        return jsonify({"ok": False, "error": "Lead has no email address"}), 400
    record = start_lead_nurture_sequence(lead)
    if not record:
        return jsonify({"ok": False, "error": "Nurture disabled or sequence already active"}), 400
    return jsonify({"ok": True, "nurture_id": record["nurture_id"]})


@app.route("/dashboard/api/lead-nurtures/<nurture_id>/stop", methods=["POST"])
@require_auth
def api_stop_lead_nurture(nurture_id):
    nurtures = load_lead_nurtures()
    for n in nurtures:
        if n["nurture_id"] == nurture_id:
            n["status"]         = "stopped"
            n["stopped_reason"] = "manual"
            n["stopped_at"]     = datetime.now(timezone.utc).isoformat()
            save_lead_nurtures(nurtures)
            return jsonify({"ok": True})
    return jsonify({"error": "Not found"}), 404


@app.route("/dashboard/api/jobs/<job_id>/comms", methods=["GET"])
@require_auth
def api_job_comms_get(job_id):
    comms = [c for c in load_job_comms() if c["job_id"] == job_id]
    comms.sort(key=lambda c: c["timestamp"])
    return jsonify(comms)

@app.route("/dashboard/api/jobs/<job_id>/comms", methods=["POST"])
@require_auth
def api_job_comms_post(job_id):
    data = request.get_json() or {}
    comm_type = data.get("type", "note")
    direction = data.get("direction", "internal")
    subject   = data.get("subject", "").strip()
    body      = data.get("body", "").strip()
    if not subject and not body:
        return jsonify({"ok": False, "error": "Subject or body required"}), 400
    user = getattr(g, "user", {})
    sent_by = user.get("username", "unknown") if isinstance(user, dict) else "unknown"
    log_job_comm(job_id, comm_type, direction, subject, body, sent_by=sent_by)
    return jsonify({"ok": True})

@app.route("/dashboard/api/jobs/<job_id>/comms/<comm_id>", methods=["DELETE"])
@require_auth
def api_job_comms_delete(job_id, comm_id):
    comms = load_job_comms()
    comms = [c for c in comms if not (c["job_id"] == job_id and c["comm_id"] == comm_id)]
    save_job_comms(comms)
    return jsonify({"ok": True})

@app.route("/dashboard/api/jobs/<job_id>/send-email", methods=["POST"])
@require_auth
def api_job_send_email(job_id):
    data    = request.get_json() or {}
    to      = data.get("to_email", "").strip()
    subject = data.get("subject", "").strip()
    body    = data.get("body", "").strip()
    if not to or not subject or not body:
        return jsonify({"ok": False, "error": "Missing fields"}), 400
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = f"Pacific Construction <{GMAIL_SENDER}>"
        msg["To"]      = to
        msg.attach(MIMEText(body, "plain"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_SENDER, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_SENDER, to, msg.as_string())
        user = getattr(g, "user", {})
        sent_by = user.get("username", "unknown") if isinstance(user, dict) else "unknown"
        log_job_comm(job_id, "email", "outbound", subject, body, sent_by=sent_by)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/dashboard/api/leads/<lead_id>/comms", methods=["GET"])
@require_auth
def api_lead_comms_get(lead_id):
    comms = [c for c in load_lead_comms() if c["lead_id"] == lead_id]
    comms.sort(key=lambda c: c["timestamp"])
    return jsonify(comms)


@app.route("/dashboard/api/leads/<lead_id>/comms", methods=["POST"])
@require_auth
def api_lead_comms_post(lead_id):
    data = request.get_json() or {}
    comm_type = data.get("type", "note")
    direction = data.get("direction", "outbound")
    subject   = data.get("subject", "").strip()
    body      = data.get("body", "").strip()
    if not subject and not body:
        return jsonify({"ok": False, "error": "Subject or body required"}), 400
    user = getattr(g, "user", {})
    sent_by = user.get("username", "unknown") if isinstance(user, dict) else "unknown"
    log_lead_comm(lead_id, comm_type, direction, subject, body, sent_by=sent_by)
    return jsonify({"ok": True})


@app.route("/dashboard/api/leads/<lead_id>/comms/<comm_id>", methods=["DELETE"])
@require_auth
def api_lead_comms_delete(lead_id, comm_id):
    comms = load_lead_comms()
    before = len(comms)
    comms = [c for c in comms if not (c["lead_id"] == lead_id and c["comm_id"] == comm_id)]
    if len(comms) == before:
        return jsonify({"error": "Not found"}), 404
    save_lead_comms(comms)
    return jsonify({"ok": True})


@app.route("/dashboard/api/jobs/<job_id>/schedule", methods=["POST"])
@require_auth
def api_job_schedule(job_id):
    """Create a Google Calendar event from a job comm note suggestion."""
    data       = request.get_json() or {}
    title      = data.get("title", "").strip()
    start_iso  = data.get("start", "")
    end_iso    = data.get("end", "")
    notes      = data.get("notes", "").strip()
    client_email = data.get("lead_email", "").strip()

    if not title or not start_iso:
        return jsonify({"ok": False, "error": "Title and start time required"}), 400

    try:
        service = get_calendar_service()
    except Exception as e:
        return jsonify({"ok": False, "error": f"Google Calendar not connected: {e}"}), 500

    try:
        event = {
            "summary": title,
            "description": notes,
            "start": {"dateTime": start_iso, "timeZone": "America/Los_Angeles"},
            "end":   {"dateTime": end_iso or start_iso, "timeZone": "America/Los_Angeles"},
        }
        if client_email:
            event["attendees"] = [{"email": client_email}]
        created = service.events().insert(calendarId=_get_calendar_id(), body=event).execute()
        user = getattr(g, "user", {})
        sent_by = user.get("username", "system") if isinstance(user, dict) else "system"
        log_job_comm(job_id, "note", "internal",
                     f"📅 Calendar event created: {title}",
                     f"Scheduled for {start_iso[:10]}. {notes}", sent_by=sent_by)
        raw_link = created.get("htmlLink", "")
        cal_email = _integ_val("CALENDAR_EMAIL") or ""
        if cal_email and raw_link:
            sep = "&" if "?" in raw_link else "?"
            raw_link = f"{raw_link}{sep}authuser={cal_email}"
        return jsonify({"ok": True, "event_id": created.get("id"), "link": raw_link})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/dashboard/api/leads/<lead_id>/schedule", methods=["POST"])
@require_auth
def api_lead_schedule(lead_id):
    """Create a Google Calendar event from a lead note suggestion."""
    data      = request.get_json() or {}
    title     = data.get("title", "").strip()
    start_iso = data.get("start", "")   # ISO datetime string
    end_iso   = data.get("end", "")
    notes     = data.get("notes", "").strip()
    lead_name = data.get("lead_name", "").strip()
    lead_email= data.get("lead_email", "").strip()

    if not title or not start_iso:
        return jsonify({"ok": False, "error": "Title and start time required"}), 400

    try:
        service = get_calendar_service()
    except Exception as e:
        return jsonify({"ok": False, "error": f"Google Calendar not connected: {e}"}), 500

    try:
        event = {
            "summary": title,
            "description": notes,
            "start": {"dateTime": start_iso, "timeZone": "America/Los_Angeles"},
            "end":   {"dateTime": end_iso or start_iso, "timeZone": "America/Los_Angeles"},
        }
        if lead_email:
            event["attendees"] = [{"email": lead_email}]
        created = service.events().insert(calendarId=_get_calendar_id(), body=event).execute()
        # Log to lead comms
        user = getattr(g, "user", {})
        sent_by = user.get("username", "system") if isinstance(user, dict) else "system"
        log_lead_comm(lead_id, "note", "internal",
                      f"📅 Calendar event created: {title}",
                      f"Scheduled for {start_iso[:10]}. {notes}", sent_by=sent_by)
        raw_link = created.get("htmlLink", "")
        cal_email = _integ_val("CALENDAR_EMAIL") or ""
        if cal_email and raw_link:
            sep = "&" if "?" in raw_link else "?"
            raw_link = f"{raw_link}{sep}authuser={cal_email}"
        return jsonify({"ok": True, "event_id": created.get("id"), "link": raw_link})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/dashboard/api/appointments")
def dashboard_appointments():
    try:
        service = get_calendar_service()
        now = datetime.now(timezone.utc)
        end = now + timedelta(days=90)
        result = service.events().list(
            calendarId=_get_calendar_id(),
            timeMin=now.isoformat(),
            timeMax=end.isoformat(),
            singleEvents=True,
            orderBy="startTime"
        ).execute()
        events = []
        for e in result.get("items", []):
            start = e.get("start", {}).get("dateTime") or e.get("start", {}).get("date", "")
            end   = e.get("end",   {}).get("dateTime") or e.get("end",   {}).get("date", "")
            events.append({
                "id": e.get("id"),
                "title": e.get("summary", "Appointment"),
                "start": start,
                "end": end,
                "description": e.get("description", ""),
                "link": e.get("htmlLink", ""),
            })
        return jsonify(events)
    except Exception as e:
        return jsonify([])


@app.route("/dashboard/api/stats")
def dashboard_stats():
    leads = load_leads()

    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    total = len(leads)
    hot = sum(1 for l in leads if "Hot" in l.get("score", ""))
    warm = sum(1 for l in leads if "Warm" in l.get("score", ""))
    cold = sum(1 for l in leads if "Cold" in l.get("score", ""))
    this_week = sum(
        1 for l in leads
        if l.get("timestamp", "") >= week_ago.isoformat()
    )
    return jsonify({
        "total": total,
        "hot": hot,
        "warm": warm,
        "cold": cold,
        "this_week": this_week,
    })


# ── People (staff & subcontractors) routes ──

@app.route("/dashboard/api/people", methods=["GET"])
@require_auth
def get_people():
    people = load_people()
    people.sort(key=lambda x: (x.get("type", ""), x.get("name", "").lower()))
    return jsonify(people)


@app.route("/dashboard/api/people", methods=["POST"])
@require_auth
def create_person():
    data = request.json or {}
    people = load_people()
    person = {
        "person_id": str(uuid.uuid4()),
        "name": data.get("name", "").strip(),
        "type": data.get("type", "employee"),      # employee | subcontractor
        "role": data.get("role", "").strip(),       # job title / trade
        "company": data.get("company", "").strip(), # subs: company name
        "phone": data.get("phone", "").strip(),
        "email": data.get("email", "").strip(),
        "notes": data.get("notes", "").strip(),
        "pay_type": data.get("pay_type", ""),       # hourly | salary | per_job | contract
        "pay_rate": float(data.get("pay_rate") or 0),
        "pay_terms": data.get("pay_terms", ""),     # Net 30, Net 15, Due on Receipt, etc.
        "qb_type": data.get("qb_type", ""),         # employee | vendor (for QB mapping)
        "tax_id": data.get("tax_id", "").strip(),   # EIN/SSN last 4 for 1099/W2
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    people.append(person)
    save_people(people)
    return jsonify(person), 201


@app.route("/dashboard/api/people/<person_id>", methods=["PUT"])
@require_auth
def update_person(person_id):
    data = request.json or {}
    people = load_people()
    for p in people:
        if p["person_id"] == person_id:
            comp_fields = {"pay_type", "pay_rate", "pay_terms", "qb_type", "tax_id"}
            comp_changed = any(k in data and data[k] != p.get(k) for k in comp_fields)
            for k in ("name", "type", "role", "company", "phone", "email", "notes",
                      "pay_type", "pay_terms", "qb_type", "tax_id", "department"):
                if k in data:
                    p[k] = str(data[k]).strip()
            for k in ("pay_rate",):
                if k in data:
                    p[k] = float(data[k] or 0)
            if comp_changed:
                from datetime import datetime
                p["comp_last_modified"] = datetime.now().strftime("%Y-%m-%d")
            save_people(people)
            return jsonify(p)
    return jsonify({"error": "Not found"}), 404


@app.route("/dashboard/api/people/<person_id>", methods=["DELETE"])
@require_auth
def delete_person(person_id):
    people = load_people()
    people = [p for p in people if p["person_id"] != person_id]
    save_people(people)
    return jsonify({"ok": True})


# ── Payroll routes ──

@app.route("/dashboard/api/payroll", methods=["GET"])
@require_auth
def get_payroll():
    person_id = request.args.get("person_id")
    records = load_payroll()
    if person_id:
        records = [r for r in records if r.get("person_id") == person_id]
    records.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return jsonify(records)


@app.route("/dashboard/api/payroll", methods=["POST"])
@require_auth
def create_pay_record():
    data = request.json or {}
    records = load_payroll()
    record = {
        "pay_id": str(uuid.uuid4()),
        "person_id": data.get("person_id", ""),
        "job_id": data.get("job_id", ""),
        "job_number": data.get("job_number", ""),
        "description": data.get("description", "").strip(),
        "amount_due": float(data.get("amount_due") or 0),
        "amount_paid": float(data.get("amount_paid") or 0),
        "status": data.get("status", "pending"),   # pending | partial | paid
        "pay_date": data.get("pay_date", ""),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    records.append(record)
    save_payroll(records)
    return jsonify(record), 201


@app.route("/dashboard/api/payroll/<pay_id>", methods=["PUT"])
@require_auth
def update_pay_record(pay_id):
    data = request.json or {}
    records = load_payroll()
    for r in records:
        if r["pay_id"] == pay_id:
            for k in ("description", "job_id", "job_number", "status", "pay_date"):
                if k in data:
                    r[k] = str(data[k]).strip()
            for k in ("amount_due", "amount_paid"):
                if k in data:
                    r[k] = float(data[k] or 0)
            save_payroll(records)
            return jsonify(r)
    return jsonify({"error": "Not found"}), 404


@app.route("/dashboard/api/payroll/<pay_id>", methods=["DELETE"])
@require_auth
def delete_pay_record(pay_id):
    records = load_payroll()
    records = [r for r in records if r["pay_id"] != pay_id]
    save_payroll(records)
    return jsonify({"ok": True})


# ── Auth routes ───────────────────────────────────────────────────────────────

@app.route("/dashboard/api/login", methods=["POST"])
def dashboard_login():
    data = request.json or {}
    username = data.get("username", "").strip().lower()
    password = data.get("password", "")

    # Fallback: legacy single-password mode (username may be blank)
    users = load_users()
    user = next((u for u in users if u.get("username", "").lower() == username and u.get("active", True)), None)

    if user and check_password_hash(user.get("password_hash", ""), password):
        session["user_id"] = user["user_id"]
        # Update last_login
        user["last_login"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        save_users(users)
        safe = {k: user[k] for k in ("user_id", "username", "display_name", "role", "permissions") if k in user}
        return jsonify({"ok": True, "user": safe})

    # Legacy fallback — single password for owner
    if not username and password == MASTER_PASSWORD:
        # Return a pseudo-owner session without DB
        session["user_id"] = "owner-jay"
        return jsonify({"ok": True, "user": {"role": "owner", "display_name": "Jay", "permissions": {}}})

    return jsonify({"ok": False, "error": "Invalid username or password"}), 401


@app.route("/dashboard/api/logout", methods=["POST"])
def dashboard_logout():
    session.clear()
    return jsonify({"ok": True})


@app.route("/dashboard/api/me", methods=["GET"])
def dashboard_me():
    user = get_current_user()
    if not user:
        # Check legacy single-password session
        if session.get("user_id") == "owner-jay":
            return jsonify({"ok": True, "user": {"role": "owner", "display_name": "Jay", "permissions": {}}})
        return jsonify({"ok": False}), 401
    safe = {k: user[k] for k in ("user_id", "username", "display_name", "role", "permissions") if k in user}
    return jsonify({"ok": True, "user": safe})


# ── Users management ──────────────────────────────────────────────────────────

ALL_PERMISSIONS = {"leads": True, "appointments": True, "jobs": True,
                   "invoices": True, "jobcosts": True, "people": True, "payroll": True, "settings": True}


@app.route("/dashboard/api/users", methods=["GET"])
def list_users():
    users = load_users()
    result = []
    for u in users:
        safe = {k: u[k] for k in u if k != "password_hash"}
        if u.get("role") == "owner":
            safe["permissions"] = ALL_PERMISSIONS.copy()
        result.append(safe)
    return jsonify(result)


@app.route("/dashboard/api/users", methods=["POST"])
def create_user():
    data = request.json or {}
    users = load_users()

    username = data.get("username", "").strip().lower()
    if not username:
        return jsonify({"error": "Username required"}), 400
    if any(u["username"].lower() == username for u in users):
        return jsonify({"error": "Username already exists"}), 400

    password = data.get("password", "").strip()
    if not password or len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400

    default_perms = {"leads": True, "appointments": True, "jobs": True,
                     "invoices": True, "jobcosts": True, "people": True, "payroll": False, "settings": False}
    new_user = {
        "user_id":          str(uuid.uuid4()),
        "username":         username,
        "display_name":     data.get("display_name", username).strip(),
        "password_hash":    generate_password_hash(password),
        "role":             data.get("role", "staff"),
        "permissions":      data.get("permissions", default_perms),
        "linked_person_id": data.get("linked_person_id") or None,
        "created_at":       datetime.now().strftime("%Y-%m-%d"),
        "last_login":       None,
        "active":           True,
    }
    users.append(new_user)
    save_users(users)
    safe = {k: new_user[k] for k in new_user if k != "password_hash"}
    return jsonify(safe), 201


@app.route("/dashboard/api/users/<user_id>", methods=["PUT"])
def update_user(user_id):
    data = request.json or {}
    users = load_users()
    user = next((u for u in users if u["user_id"] == user_id), None)
    if not user:
        return jsonify({"error": "Not found"}), 404

    for field in ("display_name", "role", "active", "linked_person_id"):
        if field in data:
            user[field] = data[field]
    if "permissions" in data:
        # Merge so a single-key update doesn't wipe other permissions
        user["permissions"] = {**user.get("permissions", {}), **data["permissions"]}

    if data.get("password"):
        if len(data["password"]) < 6:
            return jsonify({"error": "Password must be at least 6 characters"}), 400
        user["password_hash"] = generate_password_hash(data["password"])

    save_users(users)
    safe = {k: user[k] for k in user if k != "password_hash"}
    return jsonify(safe)


@app.route("/dashboard/api/users/<user_id>", methods=["DELETE"])
def delete_user(user_id):
    users = load_users()
    user = next((u for u in users if u["user_id"] == user_id), None)
    if not user:
        return jsonify({"error": "Not found"}), 404
    if user.get("role") == "owner":
        return jsonify({"error": "Cannot delete owner account"}), 403
    users = [u for u in users if u["user_id"] != user_id]
    save_users(users)
    return jsonify({"ok": True})


# ── Settings ──────────────────────────────────────────────────────────────────

@app.route("/dashboard/api/settings/change-master-password", methods=["POST"])
def change_master_password():
    data = request.json or {}
    current = data.get("current_password", "")
    new_pw  = data.get("new_password", "").strip()

    users = load_users()
    owner = next((u for u in users if u.get("role") == "owner"), None)

    # Verify current password
    if owner:
        valid = check_password_hash(owner.get("password_hash", ""), current)
    else:
        valid = (current == MASTER_PASSWORD)

    if not valid:
        return jsonify({"ok": False, "error": "Current password is incorrect"}), 401
    if len(new_pw) < 8:
        return jsonify({"ok": False, "error": "New password must be at least 8 characters"}), 400

    if owner:
        owner["password_hash"] = generate_password_hash(new_pw)
        save_users(users)
    return jsonify({"ok": True})


# ── General Settings sections ─────────────────────────────────────────────────

SETTINGS_SECTIONS = {"company", "notifications", "billing", "jobs", "dashboard", "followup", "lead_nurture"}

@app.route("/dashboard/api/settings/<section>", methods=["GET"])
def get_settings_section(section):
    if section not in SETTINGS_SECTIONS:
        return jsonify({"error": "Unknown section"}), 404
    cfg = load_config()
    defaults = DEFAULT_SETTINGS.get(section, {})
    merged = {**defaults, **cfg.get(section, {})}
    return jsonify(merged)

@app.route("/dashboard/api/settings/<section>", methods=["POST"])
def save_settings_section(section):
    if section not in SETTINGS_SECTIONS:
        return jsonify({"error": "Unknown section"}), 404
    data = request.json or {}
    cfg = load_config()
    existing = cfg.get(section, {})
    existing.update(data)
    cfg[section] = existing
    save_config(cfg)
    return jsonify({"ok": True})

@app.route("/dashboard/api/settings/logo", methods=["POST"])
def upload_logo():
    if "logo" not in request.files:
        return jsonify({"error": "No file"}), 400
    f = request.files["logo"]
    if not f.filename:
        return jsonify({"error": "No file selected"}), 400
    ext = f.filename.rsplit(".", 1)[-1].lower()
    if ext not in ("png", "jpg", "jpeg", "gif", "webp", "svg"):
        return jsonify({"error": "Invalid file type"}), 400
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    os.makedirs(static_dir, exist_ok=True)
    logo_path = os.path.join(static_dir, f"company_logo.{ext}")
    f.save(logo_path)
    cfg = load_config()
    cfg["logo_url"] = f"/static/company_logo.{ext}"
    save_config(cfg)
    return jsonify({"ok": True, "url": f"/static/company_logo.{ext}"})

@app.route("/dashboard/api/settings/company-public", methods=["GET"])
def company_public():
    cfg = load_config()
    co = {**DEFAULT_SETTINGS["company"], **cfg.get("company", {})}
    return jsonify({k: co[k] for k in ("name","address","city","state","zip","phone","email","website","tax_rate","logo_url") if k in co or k == "logo_url"})

def _integ_val(key):
    """Return integration credential: config.json overrides .env."""
    cfg = load_config().get("integrations", {})
    return cfg.get(key) or os.getenv(key, "")


@app.route("/dashboard/api/settings/integrations", methods=["GET"])
def settings_integrations():
    cal_connected = os.path.exists(CALENDAR_TOKEN)
    gmail_sender  = _integ_val("GMAIL_SENDER")
    gmail_pw      = _integ_val("GMAIL_APP_PASSWORD")
    twilio_sid    = _integ_val("TWILIO_ACCOUNT_SID")
    twilio_token  = _integ_val("TWILIO_AUTH_TOKEN")
    sheets_hook   = _integ_val("SHEETS_WEBHOOK")
    inbox_email = _integ_val("INVOICE_INBOX_EMAIL")
    inbox_pw    = _integ_val("INVOICE_INBOX_PASSWORD")
    return jsonify({
        "google_calendar":    cal_connected,
        "calendar_id":        _integ_val("CALENDAR_ID"),
        "calendar_email":     _integ_val("CALENDAR_EMAIL"),
        "gmail":              bool(gmail_sender) and bool(gmail_pw),
        "gmail_sender":       gmail_sender,
        "twilio":             bool(twilio_sid) and bool(twilio_token),
        "twilio_phone":       _integ_val("TWILIO_FROM"),
        "lead_notify_email":  _integ_val("LEAD_NOTIFY_EMAIL"),
        "sheets_webhook":     bool(sheets_hook),
        "invoice_inbox":      bool(inbox_email) and bool(inbox_pw),
        "invoice_inbox_email": inbox_email,
    })


DEV_PASSWORD_DEFAULT = os.getenv("DEV_PASSWORD", "")

def _check_dev_password(password):
    """Return True if password matches the stored dev password (or default)."""
    cfg = load_config()
    stored_hash = cfg.get("dev_password_hash")
    if stored_hash:
        return check_password_hash(stored_hash, password)
    # Fall back to hardcoded default if never set
    return password == DEV_PASSWORD_DEFAULT


@app.route("/dashboard/api/verify-dev-access", methods=["POST"])
def verify_dev_access():
    data = request.json or {}
    if _check_dev_password(data.get("password", "")):
        session["dev_unlocked"] = True
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "Incorrect developer password"}), 401


@app.route("/dashboard/api/settings/set-dev-password", methods=["POST"])
def set_dev_password():
    data = request.json or {}
    if not _check_dev_password(data.get("current_password", "")):
        return jsonify({"ok": False, "error": "Incorrect current developer password"}), 401
    new_pw = data.get("new_password", "").strip()
    if len(new_pw) < 8:
        return jsonify({"ok": False, "error": "Password must be at least 8 characters"}), 400
    cfg = load_config()
    cfg["dev_password_hash"] = generate_password_hash(new_pw)
    save_config(cfg)
    return jsonify({"ok": True})


@app.route("/dashboard/api/settings/integration", methods=["POST"])
def save_integration():
    if not session.get("dev_unlocked"):
        return jsonify({"ok": False, "error": "Developer access required"}), 403
    data = request.json or {}
    allowed_fields = {
        "GMAIL_SENDER", "GMAIL_APP_PASSWORD", "LEAD_NOTIFY_EMAIL",
        "TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_FROM",
        "SHEETS_WEBHOOK", "CALENDAR_ID", "CALENDAR_EMAIL"
    }
    cfg = load_config()
    integ = cfg.get("integrations", {})
    for k, v in data.items():
        if k in allowed_fields and v:
            integ[k] = v
    cfg["integrations"] = integ
    save_config(cfg)
    # Also update os.environ so changes take effect without restart
    for k, v in integ.items():
        if k in allowed_fields:
            os.environ[k] = v
    return jsonify({"ok": True})

@app.route("/dashboard/api/data/export", methods=["GET"])
def export_data():
    import zipfile, io as _io
    buf = _io.BytesIO()
    ts = datetime.now().strftime("%Y%m%d-%H%M")
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for fname in ["jobs.json", "payroll.json", "people.json", "invoices.json", "config.json", LEADS_FILE]:
            if os.path.exists(fname):
                zf.write(fname)
    buf.seek(0)
    from flask import send_file
    return send_file(buf, mimetype="application/zip", as_attachment=True,
                     download_name=f"pacific-construction-backup-{ts}.zip")

@app.route("/dashboard/api/data/summary", methods=["GET"])
def data_summary():
    jobs     = load_jobs()
    invoices = load_invoices()
    people   = load_people()
    payroll  = load_payroll()
    leads_count = len(load_leads())
    return jsonify({
        "jobs": len(jobs),
        "invoices": len(invoices),
        "people": len(people),
        "payroll": len(payroll),
        "leads": leads_count
    })


# ── Compensation PIN ──────────────────────────────────────────────────────────

@app.route("/dashboard/api/verify-comp-pin", methods=["POST"])
def verify_comp_pin():
    data = request.json or {}
    cfg  = load_config()
    if data.get("pin") == cfg.get("comp_pin", "1234"):
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "Incorrect PIN"}), 401


@app.route("/dashboard/api/change-comp-pin", methods=["POST"])
def change_comp_pin():
    data = request.json or {}
    if data.get("master_password") != MASTER_PASSWORD:
        return jsonify({"ok": False, "error": "Incorrect master password"}), 403
    new_pin = str(data.get("new_pin", "")).strip()
    if not new_pin.isdigit() or len(new_pin) != 4:
        return jsonify({"ok": False, "error": "PIN must be exactly 4 digits"}), 400
    cfg = load_config()
    cfg["comp_pin"] = new_pin
    from datetime import datetime
    cfg["comp_pin_changed"] = datetime.now().strftime("%Y-%m-%d")
    save_config(cfg)
    return jsonify({"ok": True})


@app.route("/dashboard/api/people/<person_id>/recalculate-pending", methods=["POST"])
@require_auth
def recalculate_pending(person_id):
    """Recalculate amount_due on all pending pay records after a rate change."""
    data      = request.json or {}
    pay_type  = data.get("pay_type", "salary")
    pay_rate  = float(data.get("pay_rate", 0))
    pay_terms = data.get("pay_terms", "biweekly")

    if pay_type == "salary":
        divisor   = 52 if pay_terms == "weekly" else 26
        new_amount = round(pay_rate / divisor, 2)
    elif pay_type == "hourly":
        hours     = 40 if pay_terms == "weekly" else 80
        new_amount = round(pay_rate * hours, 2)
    else:
        return jsonify({"ok": True, "updated": 0, "new_amount": 0})

    records = load_payroll()
    updated = 0
    for r in records:
        if r.get("person_id") == person_id and r.get("status") in ("pending", ""):
            r["amount_due"]  = new_amount
            r["amount_paid"] = 0.0
            updated += 1
    save_payroll(records)
    return jsonify({"ok": True, "updated": updated, "new_amount": new_amount})


# ── Pay stub viewer ──

@app.route("/dashboard/paystub/<pay_id>")
def view_paystub(pay_id):
    records  = load_payroll()
    record   = next((r for r in records if r["pay_id"] == pay_id), None)
    if not record:
        return "<h3 style='font-family:sans-serif;padding:40px;color:#888'>Pay record not found.</h3>", 404
    people = load_people()
    person = next((p for p in people if p["person_id"] == record["person_id"]), {})

    pay_date = record.get("pay_date", "")
    ytd_year = pay_date[:4]  # current year only
    ytd_recs = [r for r in records
                if r["person_id"] == record["person_id"]
                and r.get("pay_date", "")[:4] == ytd_year
                and r.get("pay_date", "") <= pay_date
                and r.get("status") in ("paid", "partial")]
    ytd_gross  = sum(r["amount_due"]   for r in ytd_recs)
    ytd_paid   = sum(r["amount_paid"]  for r in ytd_recs)

    return _paystub_html(record, person, ytd_gross, ytd_paid)


def _paystub_html(record, person, ytd_gross, ytd_paid):
    from markupsafe import escape as e
    co_cfg = load_config().get("company", DEFAULT_SETTINGS["company"])
    co_name = co_cfg.get("name", "Pacific Construction")
    co_addr = f"{co_cfg.get('address','')}, {co_cfg.get('city','')}, {co_cfg.get('state','')} {co_cfg.get('zip','')}"
    co_phone = co_cfg.get("phone", "")

    is_employee = person.get("qb_type") == "employee"
    gross       = float(record.get("amount_paid") or 0)
    amount_due  = float(record.get("amount_due")  or 0)
    pay_date      = record.get("pay_date", "—")
    period_start  = record.get("period_start", "")
    period_end    = record.get("period_end", "")
    description   = record.get("description", "—")
    job_num       = record.get("job_number", "")
    stub_num      = record.get("pay_id", "")[:8].upper()

    # Format dates nicely
    try:
        from datetime import datetime as dt
        pay_date_fmt = dt.strptime(pay_date, "%Y-%m-%d").strftime("%B %d, %Y")
    except Exception:
        pay_date_fmt = pay_date

    try:
        period_fmt = (dt.strptime(period_start, "%Y-%m-%d").strftime("%b %d, %Y")
                      + " – " + dt.strptime(period_end, "%Y-%m-%d").strftime("%b %d, %Y"))
    except Exception:
        period_fmt = ""

    # Pay type display
    pay_type_map  = {"hourly":"Hourly","salary":"Salary","per_job":"Per Job","contract":"Contract"}
    terms_map     = {"immediate":"Due on Receipt","net15":"Net 15","net30":"Net 30",
                     "weekly":"Weekly","biweekly":"Bi-Weekly","monthly":"Monthly"}
    pay_type_str  = pay_type_map.get(person.get("pay_type",""), person.get("pay_type",""))
    pay_rate      = float(person.get("pay_rate") or 0)
    pay_terms_str = terms_map.get(person.get("pay_terms",""), person.get("pay_terms",""))

    # WA state: no state income tax
    fed_rate  = 0.22
    ss_rate   = 0.062
    med_rate  = 0.0145

    if is_employee:
        fed_tax  = round(gross * fed_rate, 2)
        ss_tax   = round(gross * ss_rate,  2)
        med_tax  = round(gross * med_rate, 2)
        total_ded = round(fed_tax + ss_tax + med_tax, 2)
        net_pay   = round(gross - total_ded, 2)

        ytd_fed   = round(ytd_paid * fed_rate, 2)
        ytd_ss    = round(ytd_paid * ss_rate,  2)
        ytd_med   = round(ytd_paid * med_rate, 2)
        ytd_net   = round(ytd_paid - ytd_fed - ytd_ss - ytd_med, 2)

        rate_line = ""
        if pay_rate and pay_type_str == "Hourly":
            rate_line = f"<div class='info-row'><span class='lbl'>Pay Rate</span><span>${pay_rate:,.2f} / hr</span></div>"
        elif pay_rate and pay_type_str == "Salary":
            rate_line = f"<div class='info-row'><span class='lbl'>Annual Salary</span><span>${pay_rate:,.0f}</span></div>"

        pay_terms_raw = person.get("pay_terms", "")
        if pay_terms_raw == "weekly":
            period_label = "Weekly Pay"
            divisor_note = f" (${pay_rate:,.0f}/yr ÷ 52)" if pay_rate and pay_type_str == "Salary" else ""
        else:
            period_label = "Bi-Weekly Pay"
            divisor_note = f" (${pay_rate:,.0f}/yr ÷ 26)" if pay_rate and pay_type_str == "Salary" else ""

        earn_label = f"{period_label} — {period_fmt}" if period_fmt else e(description)
        if pay_rate and pay_type_str == "Hourly":
            hrs = 40 if pay_terms_raw == "weekly" else 80
            earn_detail = f" ({hrs} hrs @ ${pay_rate:,.2f}/hr)"
        elif pay_rate and pay_type_str == "Salary":
            earn_detail = divisor_note
        else:
            earn_detail = ""

        earnings_block = f"""
        <div class='section-head'>Earnings</div>
        <table class='amt-table'>
          <tr><th>Description</th><th>Current</th><th>YTD</th></tr>
          <tr><td>{earn_label}{earn_detail}</td><td>${gross:,.2f}</td><td>${ytd_gross:,.2f}</td></tr>
        </table>

        <div class='section-head'>Deductions</div>
        <table class='amt-table'>
          <tr><th>Description</th><th>Current</th><th>YTD</th></tr>
          <tr><td>Federal Income Tax (est. {int(fed_rate*100)}%)</td><td>${fed_tax:,.2f}</td><td>${ytd_fed:,.2f}</td></tr>
          <tr><td>WA State Income Tax</td><td>$0.00</td><td>$0.00</td></tr>
          <tr><td>Social Security (6.2%)</td><td>${ss_tax:,.2f}</td><td>${ytd_ss:,.2f}</td></tr>
          <tr><td>Medicare (1.45%)</td><td>${med_tax:,.2f}</td><td>${ytd_med:,.2f}</td></tr>
          <tr class='subtotal'><td><strong>Total Deductions</strong></td><td><strong>${total_ded:,.2f}</strong></td><td><strong>${ytd_fed+ytd_ss+ytd_med:,.2f}</strong></td></tr>
        </table>

        <div class='net-pay-bar'>
          <div>
            <div class='net-label'>NET PAY</div>
            <div class='net-amount'>${net_pay:,.2f}</div>
          </div>
          <div class='net-ytd'>
            <div class='net-label'>YTD NET PAY</div>
            <div class='net-ytd-amt'>${ytd_net:,.2f}</div>
          </div>
        </div>

        <div class='notice'>
          <strong>Note:</strong> Tax amounts shown are estimates for record-keeping purposes.
          Actual withholding is calculated by payroll software at time of payment.
          Washington State has no state income tax. W-2 issued annually.
        </div>
        """

        left_col = f"""
          <div class='card-label'>Employee</div>
          <div class='card-name'>{e(person.get('name','—'))}</div>
          <div class='card-sub'>{e(person.get('role',''))}</div>
          <div class='info-block'>
            <div class='info-row'><span class='lbl'>Pay Type</span><span>{pay_type_str}</span></div>
            {rate_line}
            <div class='info-row'><span class='lbl'>Pay Frequency</span><span>{pay_terms_str}</span></div>
            {f"<div class='info-row'><span class='lbl'>Pay Period</span><span>{period_fmt}</span></div>" if period_fmt else ''}
            <div class='info-row'><span class='lbl'>QB Type</span><span>W-2 Employee</span></div>
            {f"<div class='info-row'><span class='lbl'>Tax ID</span><span>***{e(person.get('tax_id',''))}</span></div>" if person.get('tax_id') else ''}
          </div>
        """

    else:  # subcontractor — remittance advice
        balance = round(amount_due - gross, 2)

        earnings_block = f"""
        <div class='section-head'>Payment Detail</div>
        <table class='amt-table'>
          <tr><th>Description</th><th>Invoice Amount</th><th>Payment</th><th>Balance</th></tr>
          <tr>
            <td>{e(description)}</td>
            <td>${amount_due:,.2f}</td>
            <td>${gross:,.2f}</td>
            <td>${balance:,.2f}</td>
          </tr>
        </table>

        <div class='net-pay-bar'>
          <div>
            <div class='net-label'>AMOUNT PAID</div>
            <div class='net-amount'>${gross:,.2f}</div>
          </div>
          <div class='net-ytd'>
            <div class='net-label'>YTD PAYMENTS</div>
            <div class='net-ytd-amt'>${ytd_paid:,.2f}</div>
          </div>
        </div>

        <div class='notice'>
          <strong>1099 Vendor — No Tax Withholding.</strong>
          Payments to this vendor are not subject to income tax withholding.
          A Form 1099-NEC will be issued if annual payments exceed $600.
          Vendor is responsible for self-employment tax obligations.
        </div>
        """

        company_line = f"<div class='card-sub'>{e(person.get('company',''))}</div>" if person.get('company') else ""
        left_col = f"""
          <div class='card-label'>Vendor / Subcontractor</div>
          <div class='card-name'>{e(person.get('name','—'))}</div>
          {company_line}
          <div class='info-block'>
            <div class='info-row'><span class='lbl'>Payment Type</span><span>{pay_type_str or 'Contract'}</span></div>
            <div class='info-row'><span class='lbl'>Payment Terms</span><span>{pay_terms_str}</span></div>
            <div class='info-row'><span class='lbl'>QB Type</span><span>1099-NEC Vendor</span></div>
            {f"<div class='info-row'><span class='lbl'>Tax ID</span><span>***{e(person.get('tax_id',''))}</span></div>" if person.get('tax_id') else ''}
          </div>
        """

    doc_type = "PAY STATEMENT" if is_employee else "REMITTANCE ADVICE"
    status_color = {"paid": "#22c55e", "partial": "#60a5fa", "pending": "#f59e0b"}.get(record.get("status",""), "#888")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{'Pay Stub' if is_employee else 'Remittance'} — {e(person.get('name',''))} — {pay_date_fmt}</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Barlow+Condensed:wght@700;800&display=swap" rel="stylesheet">
<style>
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{ font-family:'Inter',sans-serif; background:#f4f4f5; color:#111; font-size:14px; }}
  .page {{ max-width:780px; margin:32px auto; background:#fff; border-radius:12px;
           box-shadow:0 4px 32px rgba(0,0,0,0.12); overflow:hidden; }}
  @media print {{
    body {{ background:#fff; }}
    .page {{ box-shadow:none; margin:0; border-radius:0; max-width:100%; }}
    .no-print {{ display:none !important; }}
  }}

  /* Header */
  .stub-header {{ background:#0a0a0a; padding:22px 28px; display:flex; align-items:center; justify-content:space-between; }}
  .company-block .co {{ font-family:'Barlow Condensed',sans-serif; font-size:22px; font-weight:800;
    color:#fff; letter-spacing:3px; text-transform:uppercase; }}
  .company-block .addr {{ font-size:11px; color:rgba(255,255,255,0.45); margin-top:3px; }}
  .doc-type-block {{ text-align:right; }}
  .doc-type {{ font-family:'Barlow Condensed',sans-serif; font-size:18px; font-weight:800;
    color:#e8650a; letter-spacing:2px; text-transform:uppercase; }}
  .doc-num {{ font-size:10px; color:rgba(255,255,255,0.4); margin-top:4px; letter-spacing:1px; }}

  /* Status bar */
  .status-bar {{ background:#111; padding:8px 28px; display:flex; align-items:center; gap:12px;
    border-bottom:2px solid #e8650a; }}
  .status-dot {{ width:8px; height:8px; border-radius:50%; background:{status_color}; flex-shrink:0; }}
  .status-text {{ font-size:11px; font-weight:700; text-transform:uppercase;
    letter-spacing:1.5px; color:{status_color}; }}
  .status-date {{ margin-left:auto; font-size:11px; color:rgba(255,255,255,0.4); }}

  /* Two-col info row */
  .info-row-top {{ display:grid; grid-template-columns:1fr 1fr; gap:0;
    border-bottom:1px solid #e5e7eb; }}
  .info-col {{ padding:20px 28px; }}
  .info-col + .info-col {{ border-left:1px solid #e5e7eb; }}
  .card-label {{ font-size:9px; font-weight:700; text-transform:uppercase;
    letter-spacing:1.5px; color:#9ca3af; margin-bottom:6px; }}
  .card-name {{ font-size:18px; font-weight:700; }}
  .card-sub {{ font-size:12px; color:#6b7280; margin-top:2px; }}
  .info-block {{ margin-top:12px; }}
  .info-row {{ display:flex; gap:8px; padding:4px 0; font-size:12px;
    border-bottom:1px solid #f3f4f6; }}
  .info-row:last-child {{ border-bottom:none; }}
  .lbl {{ color:#9ca3af; width:110px; flex-shrink:0; font-weight:500; }}

  /* Pay date col */
  .pay-date-card-label {{ font-size:9px; font-weight:700; text-transform:uppercase;
    letter-spacing:1.5px; color:#9ca3af; margin-bottom:6px; }}
  .pay-date-val {{ font-size:18px; font-weight:700; color:#e8650a; }}
  .job-ref {{ display:inline-block; margin-top:8px; padding:3px 10px;
    background:#fff7ed; border:1px solid #fed7aa; border-radius:6px;
    font-size:11px; font-weight:700; color:#ea580c; }}

  /* Amounts sections */
  .amounts-block {{ padding:20px 28px; }}
  .section-head {{ font-size:10px; font-weight:700; text-transform:uppercase;
    letter-spacing:1.5px; color:#6b7280; padding:10px 0 6px;
    border-bottom:2px solid #e5e7eb; margin-bottom:2px; margin-top:12px; }}
  .section-head:first-child {{ margin-top:0; }}
  .amt-table {{ width:100%; border-collapse:collapse; font-size:13px; }}
  .amt-table th {{ padding:8px 10px; text-align:left; font-size:10px; font-weight:700;
    text-transform:uppercase; letter-spacing:0.8px; color:#9ca3af;
    background:#f9fafb; border-bottom:1px solid #e5e7eb; }}
  .amt-table th:not(:first-child) {{ text-align:right; }}
  .amt-table td {{ padding:9px 10px; border-bottom:1px solid #f3f4f6; }}
  .amt-table td:not(:first-child) {{ text-align:right; font-variant-numeric:tabular-nums; }}
  .amt-table tr.subtotal td {{ background:#f9fafb; border-top:2px solid #e5e7eb; }}

  /* Net pay bar */
  .net-pay-bar {{ display:flex; align-items:center; justify-content:space-between;
    background:#0a0a0a; margin-top:16px; padding:18px 20px; border-radius:8px; }}
  .net-label {{ font-size:10px; font-weight:700; text-transform:uppercase;
    letter-spacing:1.5px; color:rgba(255,255,255,0.5); margin-bottom:4px; }}
  .net-amount {{ font-size:28px; font-weight:800; color:#e8650a;
    font-family:'Barlow Condensed',sans-serif; letter-spacing:1px; }}
  .net-ytd {{ text-align:right; }}
  .net-ytd-amt {{ font-size:20px; font-weight:700; color:#fff;
    font-family:'Barlow Condensed',sans-serif; }}

  /* Notice */
  .notice {{ margin-top:14px; padding:12px 14px; background:#f9fafb;
    border-left:3px solid #e8650a; border-radius:0 6px 6px 0;
    font-size:11px; color:#6b7280; line-height:1.6; }}

  /* Footer */
  .stub-footer {{ background:#f9fafb; border-top:1px solid #e5e7eb;
    padding:14px 28px; display:flex; justify-content:space-between;
    align-items:center; }}
  .footer-left {{ font-size:10px; color:#9ca3af; line-height:1.6; }}
  .footer-right {{ display:flex; gap:8px; }}
  .btn-print {{ padding:9px 20px; background:#e8650a; border:none; border-radius:8px;
    font-size:12px; font-weight:700; color:#fff; cursor:pointer; font-family:inherit;
    letter-spacing:0.5px; transition:background .15s; }}
  .btn-print:hover {{ background:#d05a08; }}
  .btn-close {{ padding:9px 16px; background:#f3f4f6; border:1px solid #e5e7eb;
    border-radius:8px; font-size:12px; font-weight:600; color:#6b7280;
    cursor:pointer; font-family:inherit; transition:all .15s; }}
  .btn-close:hover {{ background:#e5e7eb; }}
</style>
</head>
<body>
<div class="page">

  <!-- Header -->
  <div class="stub-header">
    <div class="company-block">
      <div class="co">{co_name}</div>
      <div class="addr">{co_addr}</div>
    </div>
    <div class="doc-type-block">
      <div class="doc-type">{doc_type}</div>
      <div class="doc-num">REF # {stub_num}</div>
    </div>
  </div>

  <!-- Status bar -->
  <div class="status-bar">
    <div class="status-dot"></div>
    <div class="status-text">{record.get('status','—').upper()}</div>
    <div class="status-date">Payment Date: {pay_date_fmt}</div>
  </div>

  <!-- Info columns -->
  <div class="info-row-top">
    <div class="info-col">
      {left_col}
    </div>
    <div class="info-col">
      <div class="pay-date-card-label">Pay Date</div>
      <div class="pay-date-val">{pay_date_fmt}</div>
      {f'<span class="job-ref">📋 {e(job_num)}</span>' if job_num else ''}
      <div class="info-block" style="margin-top:16px;">
        <div class="info-row"><span class="lbl">Gross Amount</span><span>${amount_due:,.2f}</span></div>
        <div class="info-row"><span class="lbl">Amount Paid</span><span style="color:#22c55e;font-weight:700;">${gross:,.2f}</span></div>
        {'<div class="info-row"><span class="lbl">Balance Due</span><span style="color:#ef4444;font-weight:700;">$'+f'{amount_due-gross:,.2f}'+'</span></div>' if amount_due > gross else ''}
        <div class="info-row"><span class="lbl">Status</span>
          <span style="font-weight:700;color:{status_color};">{record.get('status','—').capitalize()}</span></div>
      </div>
    </div>
  </div>

  <!-- Earnings / Payment detail -->
  <div class="amounts-block">
    {earnings_block}
  </div>

  <!-- Footer -->
  <div class="stub-footer no-print">
    <div class="footer-left">
      {co_name} · Payroll &amp; Accounts Payable<br>
      Generated {datetime.now().strftime('%B %d, %Y at %I:%M %p')} · For internal use only
    </div>
    <div class="footer-right">
      <button class="btn-close no-print" onclick="window.close()">Close</button>
      <button class="btn-print" onclick="window.print()">🖨 Print / Save PDF</button>
    </div>
  </div>

</div>
</body>
</html>"""


# ── Vendor Invoice Inbox Poller ───────────────────────────────────────────────

INVOICE_INBOX_FILE = "invoice_inbox.json"

def load_invoice_inbox():
    if os.path.exists(INVOICE_INBOX_FILE):
        with file_lock(INVOICE_INBOX_FILE):
            with open(INVOICE_INBOX_FILE) as f:
                return json.load(f)
    return []

def save_invoice_inbox(data):
    with file_lock(INVOICE_INBOX_FILE):
        with open(INVOICE_INBOX_FILE, "w") as f:
            json.dump(data, f, indent=2)


def _parse_amount(text):
    """Extract the largest dollar amount from a string."""
    import re
    matches = re.findall(r'\$?([\d,]+\.?\d{0,2})', text)
    amounts = []
    for m in matches:
        try:
            amounts.append(float(m.replace(',', '')))
        except:
            pass
    return max(amounts) if amounts else 0.0


def _parse_invoice_number(text):
    """Try to extract an invoice number from text."""
    import re
    patterns = [
        r'invoice\s*#?\s*:?\s*([A-Z0-9\-]{4,20})',
        r'inv\s*#?\s*:?\s*([A-Z0-9\-]{4,20})',
        r'#\s*([A-Z0-9\-]{4,20})',
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return ""


def _parse_date(text):
    """Try to extract a date from text, return YYYY-MM-DD."""
    import re
    from datetime import datetime
    patterns = [
        r'(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})',
        r'(\w+ \d{1,2},?\s*\d{4})',
        r'(\d{4}[\/\-]\d{2}[\/\-]\d{2})',
    ]
    for p in patterns:
        m = re.search(p, text)
        if m:
            raw = m.group(1)
            for fmt in ('%m/%d/%Y','%m-%d-%Y','%B %d, %Y','%B %d %Y','%Y-%m-%d','%m/%d/%y'):
                try:
                    return datetime.strptime(raw.strip(), fmt).strftime('%Y-%m-%d')
                except:
                    pass
    return datetime.now().strftime('%Y-%m-%d')


def _parse_pdf_text(pdf_bytes):
    """Extract text from PDF bytes using pdfplumber."""
    try:
        import pdfplumber, io
        text = ""
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                text += (page.extract_text() or "") + "\n"
        return text
    except Exception as e:
        print(f"PDF parse error: {e}")
        return ""


def _categorize_from_text(text):
    """Guess category from invoice text."""
    t = text.lower()
    if any(w in t for w in ['electric','wiring','conduit','panel','lighting']):
        return 'Labor & Subs'
    if any(w in t for w in ['rental','rent','lift','crane','equipment']):
        return 'Equipment'
    if any(w in t for w in ['permit','inspection','plan check','fee','city of','county']):
        return 'Permits'
    if any(w in t for w in ['concrete','steel','lumber','supply','materials','hardware','fastener']):
        return 'Materials'
    if any(w in t for w in ['labor','install','crew','subcontract','framing','welding']):
        return 'Labor & Subs'
    return 'Other'


def _match_job_from_text(text):
    """Try to match a job number from invoice text."""
    import re
    m = re.search(r'JOB-(\d{4}-\d{3})', text, re.IGNORECASE)
    if m:
        job_num = m.group(0).upper()
        jobs = load_jobs()
        job = next((j for j in jobs if j.get('job_number','').upper() == job_num), None)
        if job:
            return job
    return None


def _send_invoice_notification(item):
    """Notify owner/bookkeeper of new incoming invoice."""
    sender  = _integ_val("GMAIL_SENDER")
    pw      = _integ_val("GMAIL_APP_PASSWORD")
    notify  = _integ_val("LEAD_NOTIFY_EMAIL") or sender
    if not sender or not pw or not notify:
        return
    try:
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        import smtplib
        cfg     = load_config().get("company", {})
        company = cfg.get("name", "Pacific Construction")
        amt_str = f"${item['amount']:,.2f}" if item['amount'] else "unknown amount"
        status  = "✅ Job matched automatically" if item.get('job_id') else "⚠️ Needs job assignment"
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"📥 New Vendor Invoice: {item['vendor_name']} — {amt_str}"
        msg["From"]    = f"{company} <{sender}>"
        msg["To"]      = notify
        html = f"""<div style="font-family:sans-serif;max-width:500px;">
            <h2 style="color:#e8650a;">New Vendor Invoice Received</h2>
            <table style="border-collapse:collapse;width:100%;">
                <tr><td style="padding:6px 0;color:#666;">From</td><td><b>{item['vendor_name']}</b></td></tr>
                <tr><td style="padding:6px 0;color:#666;">Invoice #</td><td>{item.get('invoice_ref','—')}</td></tr>
                <tr><td style="padding:6px 0;color:#666;">Amount</td><td><b style="color:#e8650a;">{amt_str}</b></td></tr>
                <tr><td style="padding:6px 0;color:#666;">Date</td><td>{item.get('date','—')}</td></tr>
                <tr><td style="padding:6px 0;color:#666;">Job Match</td><td>{status}</td></tr>
                <tr><td style="padding:6px 0;color:#666;">Category</td><td>{item.get('category','—')}</td></tr>
            </table>
            <p style="margin-top:16px;color:#666;">Log into the dashboard → Finance → Job Costs → <b>Review Queue</b> to approve or assign.</p>
        </div>"""
        msg.attach(MIMEText(html, "html"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, pw)
            server.sendmail(sender, notify, msg.as_string())
    except Exception as e:
        print(f"Invoice notification error: {e}")


def poll_invoice_inbox():
    """
    Check the designated invoice inbox (IMAP) for new emails with attachments.
    Creates draft cost records in 'pending_review' status for each invoice found.
    """
    import imaplib, email as emaillib
    from email.header import decode_header

    inbox_email = _integ_val("INVOICE_INBOX_EMAIL") or _integ_val("GMAIL_SENDER")
    inbox_pw    = _integ_val("INVOICE_INBOX_PASSWORD") or _integ_val("GMAIL_APP_PASSWORD")
    if not inbox_email or not inbox_pw:
        print("Invoice poller: no inbox credentials configured")
        return 0

    processed = load_invoice_inbox()
    seen_ids   = {r["email_message_id"] for r in processed}
    new_items  = []

    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(inbox_email, inbox_pw)
        mail.select("INBOX")

        # Search for emails with subject hints or just all unseen
        _, msg_nums = mail.search(None, 'UNSEEN')
        ids = msg_nums[0].split()
        print(f"Invoice poller: {len(ids)} unseen emails")

        for num in ids:
            _, data = mail.fetch(num, "(RFC822)")
            raw = data[0][1]
            msg = emaillib.message_from_bytes(raw)

            msg_id   = msg.get("Message-ID", f"<{uuid.uuid4()}>")
            if msg_id in seen_ids:
                continue

            # Decode subject + sender
            subj_raw = msg.get("Subject", "")
            subj_parts = decode_header(subj_raw)
            subject = " ".join(
                p.decode(enc or "utf-8") if isinstance(p, bytes) else p
                for p, enc in subj_parts
            )
            sender_raw = msg.get("From", "")
            vendor_name = sender_raw.split("<")[0].strip().strip('"') or sender_raw

            # Only process if it looks like an invoice
            invoice_keywords = ["invoice","bill","statement","receipt","payment due","amount due","inv #","inv#"]
            subject_lower = subject.lower()
            body_text = ""
            pdf_bytes  = None
            has_invoice_hint = any(k in subject_lower for k in invoice_keywords)

            # Walk MIME parts
            for part in msg.walk():
                ct   = part.get_content_type()
                disp = str(part.get("Content-Disposition", ""))
                if ct == "text/plain":
                    try: body_text += part.get_payload(decode=True).decode(errors="replace")
                    except: pass
                if ct == "text/html" and not body_text:
                    try:
                        import re
                        html = part.get_payload(decode=True).decode(errors="replace")
                        body_text += re.sub(r'<[^>]+>', ' ', html)
                    except: pass
                if ct == "application/pdf" or (disp and "attach" in disp and ".pdf" in disp.lower()):
                    pdf_bytes = part.get_payload(decode=True)
                    has_invoice_hint = True

            if not has_invoice_hint:
                # Mark as seen but skip — not an invoice
                mail.store(num, '+FLAGS', '\\Seen')
                processed.append({"email_message_id": msg_id, "skipped": True, "subject": subject})
                continue

            # Parse text
            full_text = body_text
            if pdf_bytes:
                full_text += "\n" + _parse_pdf_text(pdf_bytes)

            amount      = _parse_amount(full_text)
            inv_number  = _parse_invoice_number(full_text)
            inv_date    = _parse_date(full_text)
            category    = _categorize_from_text(full_text)
            matched_job = _match_job_from_text(full_text)

            item = {
                "inbox_id":          str(uuid.uuid4()),
                "email_message_id":  msg_id,
                "received_at":       datetime.now(timezone.utc).isoformat(),
                "subject":           subject,
                "vendor_name":       vendor_name,
                "vendor_email":      sender_raw,
                "invoice_ref":       inv_number,
                "date":              inv_date,
                "amount":            round(amount, 2),
                "category":          category,
                "job_id":            matched_job["job_id"] if matched_job else "",
                "job_number":        matched_job["job_number"] if matched_job else "",
                "client_name":       matched_job.get("client_name","") if matched_job else "",
                "description":       subject[:120],
                "parsed_text":       full_text[:2000],
                "has_pdf":           bool(pdf_bytes),
                "status":            "pending_review",
                "reviewed_by":       None,
                "cost_id":           None,  # filled when approved
                "skipped":           False,
            }
            new_items.append(item)
            processed.append(item)
            seen_ids.add(msg_id)

            # Mark as read
            mail.store(num, '+FLAGS', '\\Seen')

        mail.logout()

    except Exception as e:
        print(f"Invoice inbox poll error: {e}")
        return 0

    if new_items:
        save_invoice_inbox(processed)
        for item in new_items:
            if not item.get("skipped"):
                _send_invoice_notification(item)
        print(f"Invoice poller: {len(new_items)} new invoices queued for review")

    return len(new_items)


def _start_invoice_poller():
    """Background thread that polls the invoice inbox every 30 minutes."""
    def _loop():
        import time
        while True:
            time.sleep(1800)
            try:
                poll_invoice_inbox()
            except Exception as e:
                print(f"Invoice poller error: {e}")
    t = threading.Thread(target=_loop, daemon=True)
    t.start()


# ── Invoice Inbox API routes ───────────────────────────────────────────────────

@app.route("/dashboard/api/invoice-inbox", methods=["GET"])
@require_auth
def get_invoice_inbox():
    items = [i for i in load_invoice_inbox() if not i.get("skipped")]
    items.sort(key=lambda x: x.get("received_at",""), reverse=True)
    return jsonify(items)

@app.route("/dashboard/api/invoice-inbox/poll", methods=["POST"])
@require_auth
def trigger_invoice_poll():
    count = poll_invoice_inbox()
    return jsonify({"ok": True, "new": count})

@app.route("/dashboard/api/invoice-inbox/<inbox_id>/approve", methods=["POST"])
@require_auth
def approve_inbox_invoice(inbox_id):
    data   = request.get_json() or {}
    inbox  = load_invoice_inbox()
    item   = next((i for i in inbox if i["inbox_id"] == inbox_id), None)
    if not item:
        return jsonify({"error": "Not found"}), 404

    # Merge any edits from the review form
    for k in ("vendor_name","amount","date","category","job_id","job_number","client_name","description","invoice_ref"):
        if k in data:
            item[k] = data[k]

    # Look up job details if job_id provided
    if item.get("job_id") and not item.get("job_number"):
        jobs = load_jobs()
        job  = next((j for j in jobs if j["job_id"] == item["job_id"]), None)
        if job:
            item["job_number"]  = job.get("job_number","")
            item["client_name"] = job.get("client_name","")

    # Create cost record
    cost = {
        "cost_id":      str(uuid.uuid4()),
        "job_id":       item.get("job_id",""),
        "job_number":   item.get("job_number",""),
        "client_name":  item.get("client_name",""),
        "vendor":       item.get("vendor_name",""),
        "description":  item.get("description",""),
        "category":     item.get("category","Other"),
        "amount":       round(float(item.get("amount",0)), 2),
        "date":         item.get("date", datetime.now().strftime("%Y-%m-%d")),
        "status":       "pending",
        "invoice_ref":  item.get("invoice_ref",""),
        "notes":        f"Auto-imported from email: {item.get('subject','')}",
        "created_at":   datetime.now(timezone.utc).isoformat(),
    }
    costs = load_jobcosts()
    costs.append(cost)
    save_jobcosts(costs)

    # Update inbox item
    user = get_current_user()
    item["status"]      = "approved"
    item["cost_id"]     = cost["cost_id"]
    item["reviewed_by"] = user.get("display_name","") if user else ""
    save_invoice_inbox(inbox)

    return jsonify({"ok": True, "cost": cost})

@app.route("/dashboard/api/invoice-inbox/<inbox_id>/reject", methods=["POST"])
@require_auth
def reject_inbox_invoice(inbox_id):
    inbox = load_invoice_inbox()
    item  = next((i for i in inbox if i["inbox_id"] == inbox_id), None)
    if not item:
        return jsonify({"error": "Not found"}), 404
    user = get_current_user()
    item["status"]      = "rejected"
    item["reviewed_by"] = user.get("display_name","") if user else ""
    save_invoice_inbox(inbox)
    return jsonify({"ok": True})

@app.route("/dashboard/api/invoice-inbox/settings", methods=["GET","POST"])
@require_auth
def invoice_inbox_settings():
    cfg = load_config()
    if request.method == "POST":
        data = request.get_json() or {}
        if "invoice_inbox" not in cfg:
            cfg["invoice_inbox"] = {}
        cfg["invoice_inbox"].update(data)
        save_config(cfg)
        return jsonify({"ok": True})
    return jsonify(cfg.get("invoice_inbox", {}))


_start_followup_scheduler()
_start_invoice_poller()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
