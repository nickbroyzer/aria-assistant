"""
Leads blueprint — lead capture, dashboard lead management, nurture sequences, comms.

Routes:
  /lead                                          → POST capture lead
  /quote                                         → POST quote form submission
  /dashboard/api/leads                           → GET / POST
  /dashboard/api/leads/<id>                      → PUT
  /dashboard/api/leads/<id>/send-email           → POST
  /dashboard/api/leads/<id>/comms                → GET / POST
  /dashboard/api/leads/<id>/comms/<cid>          → DELETE
  /dashboard/api/leads/<id>/schedule             → POST
  /dashboard/api/lead-nurtures                   → GET
  /dashboard/api/lead-nurtures/start             → POST
  /dashboard/api/lead-nurtures/<id>/stop         → POST
  /dashboard/api/lead-nurtures/send-test         → POST
"""

import smtplib
import threading
import uuid
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from flask import Blueprint, jsonify, request

from utils.constants import (
    DEFAULT_SETTINGS, GMAIL_APP_PASSWORD, GMAIL_SENDER, LEAD_NOTIFY_EMAIL,
)
from utils.config import _integ_val, load_config
from utils.auth import get_current_user, load_users, require_auth
from utils.data import (
    append_lead, load_lead_comms, load_lead_meta, load_lead_nurtures,
    load_leads, save_lead_comms, save_lead_meta, save_lead_nurtures,
)
from utils.email import (
    log_lead_comm, score_lead, send_followup_email, send_lead_email,
)
from utils.memory import load_memory
from utils.activity import log_activity
from utils.sequences import (
    _render_lead_template, start_lead_nurture_sequence,
    stop_lead_nurture_sequence,
)
from utils.calendar import get_calendar_service, _get_calendar_id

leads_bp = Blueprint("leads", __name__)


# ── Public lead capture ───────────────────────────────────────────────────────

@leads_bp.route("/lead", methods=["POST"])
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

    if not name and not contact and not project_details:
        return jsonify({
            "error": "At least one of name, contact, or project_details is required",
        }), 400

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
        "session_name": session_name,
    }
    lead["score"] = score_lead(lead)

    try:
        append_lead(lead)
        meta = load_lead_meta()
        meta[lead["lead_id"]] = {"status": "new", "created_at": lead["timestamp"]}
        save_lead_meta(meta)
        send_lead_email(lead)
        send_followup_email(lead)
        threading.Thread(
            target=start_lead_nurture_sequence, args=(lead,), daemon=True,
        ).start()
        return jsonify({
            "ok": True,
            "lead_id": lead["lead_id"],
            "message": "Lead captured successfully",
        }), 201
    except Exception as e:
        return jsonify({"error": f"Failed to save lead: {str(e)}"}), 500


@leads_bp.route("/quote", methods=["POST"])
def submit_quote():
    """Handle a structured quote request form submission."""
    data = request.get_json() or {}

    name = data.get("name", "").strip()
    email = data.get("email", "").strip()

    if not name or not email:
        return jsonify({"error": "Name and email are required"}), 400

    lead = {
        "lead_id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "name": name,
        "company": data.get("company", "").strip(),
        "location": data.get("location", "").strip(),
        "contact": (
            f"{email}"
            + (f" | {data.get('phone', '').strip()}" if data.get("phone") else "")
        ),
        "email": email,
        "phone": data.get("phone", "").strip(),
        "project_details": (
            f"Service: {data.get('service', '')}, "
            f"Size: {data.get('warehouse_size', '')} sq ft, "
            f"Height: {data.get('clear_height', '')}, "
            f"Timeline: {data.get('timeline', '')}, "
            f"Notes: {data.get('notes', '')}"
        ),
        "source": "quote-form",
        "session_name": name,
    }
    lead["score"] = score_lead(lead)
    append_lead(lead)

    # Send detailed quote email
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = (
            f"Quote Request — {name} | {data.get('service', '') or 'General'}"
        )
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


# ── Dashboard leads CRUD ──────────────────────────────────────────────────────

@leads_bp.route("/dashboard/api/leads")
def dashboard_leads():
    leads = load_leads()
    meta = load_lead_meta()
    for lead in leads:
        lid = lead.get("lead_id", "")
        m = meta.get(lid, {})
        lead["status"] = m.get("status", "new")
        lead["notes"] = m.get("notes", "")
        lead["assigned_to"] = m.get("assigned_to", "")
    leads.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return jsonify(leads)


@leads_bp.route("/dashboard/api/leads", methods=["POST"])
@require_auth
def create_lead_dashboard():
    data = request.get_json() or {}
    lead = {
        "lead_id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "name": data.get("name", "").strip(),
        "company": data.get("company", "").strip(),
        "location": data.get("location", "").strip(),
        "contact": data.get("contact", "").strip(),
        "project_details": data.get("project_details", "").strip(),
        "source": data.get("source", "dashboard").strip(),
        "session_name": "",
    }
    lead["score"] = score_lead(lead)
    append_lead(lead)
    meta = load_lead_meta()
    meta[lead["lead_id"]] = {
        "status": data.get("status", "new"),
        "created_at": lead["timestamp"],
        "notes": data.get("notes", ""),
        "assigned_to": data.get("assigned_to", ""),
    }
    save_lead_meta(meta)
    log_activity(
        "lead_created",
        f"Lead {lead['name'] or 'Unknown'} added from dashboard",
        {"lead_id": lead["lead_id"]},
    )
    return jsonify(lead), 201


@leads_bp.route("/dashboard/api/leads/<lead_id>", methods=["PUT"])
@require_auth
def update_lead(lead_id):
    data = request.get_json() or {}
    meta = load_lead_meta()
    m = meta.get(lead_id, {})
    for field in ("status", "notes", "assigned_to"):
        if field in data:
            m[field] = data[field]
    meta[lead_id] = m
    save_lead_meta(meta)

    if "score" in data:
        leads = load_leads()
        for lead in leads:
            if lead.get("lead_id") == lead_id:
                lead["score"] = data["score"]
                break
        import json, os
        from utils.constants import LEADS_FILE
        from utils.file_locks import file_lock
        with file_lock(LEADS_FILE):
            with open(LEADS_FILE, "w") as f:
                for lead in leads:
                    f.write(json.dumps(lead) + "\n")
    return jsonify({"ok": True})


@leads_bp.route("/dashboard/api/leads/<lead_id>/send-email", methods=["POST"])
@require_auth
def send_lead_manual_email(lead_id):
    data = request.get_json() or {}
    to_email = data.get("to_email", "").strip()
    subject = data.get("subject", "").strip()
    body_text = data.get("body", "").strip()

    if not to_email:
        return jsonify({"ok": False, "error": "No recipient email"}), 400
    if not subject or not body_text:
        return jsonify({"ok": False, "error": "Subject and body required"}), 400

    sender = _integ_val("GMAIL_SENDER")
    pw = _integ_val("GMAIL_APP_PASSWORD")
    if not sender or not pw:
        return jsonify({
            "ok": False,
            "error": "Gmail not configured — set credentials in Settings → Integrations",
        }), 400

    cfg = load_config()
    company = {**DEFAULT_SETTINGS["company"], **cfg.get("company", {})}

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{company['name']} <{sender}>"
        msg["To"] = to_email

        html = (
            '<!DOCTYPE html><html><body style="font-family:sans-serif;color:#333;'
            'max-width:600px;margin:0 auto;padding:24px;">'
            '<div style="white-space:pre-line;font-size:14px;line-height:1.7;">'
            f'{body_text}</div>'
            '<hr style="border:none;border-top:1px solid #eee;margin:24px 0;">'
            '<div style="font-size:11px;color:#999;">'
            f"{company.get('name', '')} · {company.get('address', '')} · "
            f"{company.get('city', '')} {company.get('state', '')} "
            f"{company.get('zip', '')} · {company.get('phone', '')}</div>"
            "</body></html>"
        )
        msg.attach(MIMEText(body_text, "plain"))
        msg.attach(MIMEText(html, "html"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, pw)
            server.sendmail(sender, to_email, msg.as_string())

        log_lead_comm(
            lead_id, comm_type="email", direction="outbound",
            subject=subject, body=body_text, sent_by="user",
        )
        log_activity(
            "lead_email_sent",
            f"Email sent to {to_email}: {subject}",
            {"lead_id": lead_id, "email": to_email},
        )
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ── Lead nurture routes ───────────────────────────────────────────────────────

@leads_bp.route("/dashboard/api/lead-nurtures", methods=["GET"])
@require_auth
def list_lead_nurtures():
    return jsonify(load_lead_nurtures())


@leads_bp.route("/dashboard/api/lead-nurtures/start", methods=["POST"])
@require_auth
def api_start_lead_nurture():
    data = request.json or {}
    lead_id = data.get("lead_id", "")
    leads = load_leads()
    lead = next((l for l in leads if l.get("lead_id") == lead_id), None)
    if not lead:
        return jsonify({"ok": False, "error": "Lead not found"}), 404
    nurtures = load_lead_nurtures()
    active = next(
        (n for n in nurtures if n["lead_id"] == lead_id and n["status"] == "active"),
        None,
    )
    if active:
        return jsonify({"ok": False, "error": "Nurture already active for this lead"}), 400
    start_lead_nurture_sequence(lead)
    return jsonify({"ok": True})


@leads_bp.route("/dashboard/api/lead-nurtures/<nurture_id>/stop", methods=["POST"])
@require_auth
def api_stop_lead_nurture(nurture_id):
    nurtures = load_lead_nurtures()
    rec = next((n for n in nurtures if n["nurture_id"] == nurture_id), None)
    if not rec:
        return jsonify({"ok": False, "error": "Not found"}), 404
    stop_lead_nurture_sequence(rec["lead_id"], reason="manual")
    return jsonify({"ok": True})


@leads_bp.route("/dashboard/api/lead-nurtures/send-test", methods=["POST"])
@require_auth
def send_test_lead_nurture():
    data = request.json or {}
    to_email = data.get("to_email", "").strip()
    subject = data.get("subject", "Test Email")
    body_txt = data.get("body", "")
    step = data.get("step", 1)
    label = data.get("label", f"Step {step}")

    if not to_email:
        return jsonify({"ok": False, "error": "No recipient email"}), 400

    sender = _integ_val("GMAIL_SENDER")
    pw = _integ_val("GMAIL_APP_PASSWORD")
    if not sender or not pw:
        return jsonify({
            "ok": False,
            "error": "Gmail not configured — set credentials in Settings → Integrations",
        }), 400

    cfg = load_config()
    company = {**DEFAULT_SETTINGS["company"], **cfg.get("company", {})}

    sample_lead = {
        "lead_id": "sample",
        "name": "Sarah Chen",
        "company": "Pacific Northwest Cold Storage",
        "project_details": "Expand refrigerated warehouse",
        "contact": to_email,
    }
    rendered_subject = _render_lead_template(subject, sample_lead, company)
    rendered_body = _render_lead_template(body_txt, sample_lead, company)

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[TEST — {label}] {rendered_subject}"
        msg["From"] = f"{company['name']} <{sender}>"
        msg["To"] = to_email

        plain = f"--- TEST EMAIL (Lead Nurture Step {step}: {label}) ---\n\n{rendered_body}"
        html = (
            '<!DOCTYPE html><html><body style="font-family:sans-serif;color:#333;'
            'max-width:600px;margin:0 auto;padding:24px;">'
            '<div style="background:#fff3cd;border:1px solid #ffc107;border-radius:6px;'
            'padding:10px 14px;margin-bottom:20px;font-size:12px;color:#856404;">'
            f"  <strong>TEST EMAIL</strong> — Lead Nurture Step {step}: {label}. "
            "Sample data used.</div>"
            '<div style="white-space:pre-line;font-size:14px;line-height:1.7;">'
            f"{rendered_body}</div>"
            '<hr style="border:none;border-top:1px solid #eee;margin:24px 0;">'
            '<div style="font-size:11px;color:#999;">'
            f"{company.get('name', '')} · {company.get('address', '')} · "
            f"{company.get('city', '')} {company.get('state', '')} · "
            f"{company.get('phone', '')}</div></body></html>"
        )
        msg.attach(MIMEText(plain, "plain"))
        msg.attach(MIMEText(html, "html"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, pw)
            server.sendmail(sender, to_email, msg.as_string())
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ── Lead comms ────────────────────────────────────────────────────────────────

@leads_bp.route("/dashboard/api/leads/<lead_id>/comms", methods=["GET"])
def api_lead_comms_get(lead_id):
    comms = load_lead_comms()
    return jsonify([c for c in comms if c.get("lead_id") == lead_id])


@leads_bp.route("/dashboard/api/leads/<lead_id>/comms", methods=["POST"])
@require_auth
def api_lead_comms_post(lead_id):
    data = request.json or {}
    comms = load_lead_comms()
    user = get_current_user()
    entry = {
        "comm_id": str(uuid.uuid4()),
        "lead_id": lead_id,
        "type": data.get("type", "note"),
        "direction": data.get("direction", "internal"),
        "subject": data.get("subject", ""),
        "body": data.get("body", ""),
        "sent_by": user.get("display_name", "user") if user else "user",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    comms.append(entry)
    save_lead_comms(comms)
    return jsonify(entry), 201


@leads_bp.route("/dashboard/api/leads/<lead_id>/comms/<comm_id>", methods=["DELETE"])
@require_auth
def api_lead_comms_delete(lead_id, comm_id):
    comms = load_lead_comms()
    comms = [c for c in comms if not (c.get("lead_id") == lead_id and c.get("comm_id") == comm_id)]
    save_lead_comms(comms)
    return jsonify({"ok": True})


# ── Lead scheduling ───────────────────────────────────────────────────────────

@leads_bp.route("/dashboard/api/leads/<lead_id>/schedule", methods=["POST"])
@require_auth
def api_lead_schedule(lead_id):
    data = request.json or {}
    title = data.get("title", "").strip()
    start = data.get("start", "").strip()
    end = data.get("end", "").strip()
    description = data.get("description", "").strip()

    if not title or not start or not end:
        return jsonify({"ok": False, "error": "Title, start, and end required"}), 400

    try:
        service = get_calendar_service()
        event = {
            "summary": title,
            "description": description,
            "start": {"dateTime": start, "timeZone": "America/Los_Angeles"},
            "end": {"dateTime": end, "timeZone": "America/Los_Angeles"},
        }
        attendee_email = data.get("attendee_email", "").strip()
        if attendee_email:
            event["attendees"] = [{"email": attendee_email}]
        created = service.events().insert(
            calendarId=_get_calendar_id(), body=event, sendUpdates="all",
        ).execute()

        leads = load_leads()
        lead = next((l for l in leads if l.get("lead_id") == lead_id), None)
        lead_name = lead.get("name", "Unknown") if lead else "Unknown"
        log_activity(
            "lead_appointment",
            f"Appointment scheduled for lead {lead_name}: {title}",
            {"lead_id": lead_id, "event_id": created.get("id")},
        )
        log_lead_comm(
            lead_id, comm_type="appointment", direction="outbound",
            subject=title, body=f"Appointment: {title}", sent_by="user",
        )
        return jsonify({"ok": True, "event_id": created.get("id"), "link": created.get("htmlLink")})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
