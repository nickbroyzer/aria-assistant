"""
Central constants for the Ash assistant application.

All file paths, environment variables, system prompts, tool definitions,
and default settings live here. No internal imports — this is the base layer.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── Data File Paths ───────────────────────────────────────────────────────────
MEMORY_FILE          = "memory.json"
LEADS_FILE           = "leads.jsonl"
USER_SESSIONS_FILE   = "user_sessions.json"
USERS_FILE           = "users.json"
JOBS_FILE            = "jobs.json"
INVOICES_FILE        = "invoices.json"
JOBCOSTS_FILE        = "jobcosts.json"
PEOPLE_FILE          = "people.json"
CONFIG_FILE          = "config.json"
ACTIVITY_FILE        = "activity_log.jsonl"
PAYROLL_FILE         = "payroll.json"
FOLLOWUPS_FILE       = "followups.json"
LEAD_META_FILE       = "lead_meta.json"
LEAD_NURTURES_FILE   = "lead_nurtures.json"
LEAD_COMMS_FILE      = "lead_comms.json"
JOB_COMMS_FILE       = "job_comms.json"
VENDOR_INVOICES_FILE = "vendorinvoices.json"
INVOICE_INBOX_FILE   = "invoice_inbox.json"

# ── Identity ──────────────────────────────────────────────────────────────────
ASSISTANT_NAME = "Ash"

# ── Gmail / Integrations (env vars) ──────────────────────────────────────────
GMAIL_SENDER       = os.getenv("GMAIL_SENDER")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
LEAD_NOTIFY_EMAIL  = os.getenv("LEAD_NOTIFY_EMAIL")
SHEETS_WEBHOOK     = os.getenv("SHEETS_WEBHOOK")
DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "")

# ── Auth / Passwords ─────────────────────────────────────────────────────────
MASTER_PASSWORD      = os.getenv("MASTER_PASSWORD", os.getenv("DASHBOARD_PASSWORD", ""))
DEV_PASSWORD_DEFAULT = os.getenv("DEV_PASSWORD", "")

# ── Google Calendar ──────────────────────────────────────────────────────────
CALENDAR_TOKEN  = "google_token.json"
CALENDAR_CREDS  = "google_credentials.json"
CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar"]
BUSINESS_HOURS  = {"start": 8, "end": 17}   # 8am–5pm
SLOT_DURATION   = 60                          # minutes

# ── Gmail / Ash Scanner ───────────────────────────────────────────────────────
GMAIL_TOKEN  = "gmail_token.json"
GMAIL_CREDS  = "gmail_credentials.json"
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

# ── Settings Sections ────────────────────────────────────────────────────────
SETTINGS_SECTIONS = {"company", "notifications", "billing", "jobs", "dashboard", "followup", "lead_nurture"}

# ── System Prompt ────────────────────────────────────────────────────────────
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

# ── LLM Tool Definitions ────────────────────────────────────────────────────
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

# ── Default Settings ─────────────────────────────────────────────────────────
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
