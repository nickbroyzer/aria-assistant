"""
Email sending, lead scoring, communication logging helpers.
"""

import re
import smtplib
import uuid
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from utils.constants import GMAIL_SENDER, GMAIL_APP_PASSWORD, LEAD_NOTIFY_EMAIL
from utils.config import _integ_val, load_config
from utils.data import (
    load_lead_comms, save_lead_comms,
    load_job_comms, save_job_comms,
)


# ── Lead Scoring ──────────────────────────────────────────────────────────────

def score_lead(lead: dict) -> str:
    """Score a lead as Hot, Warm, or Cold based on available info."""
    score = 0
    details = (lead.get("project_details") or "").lower()
    contact = (lead.get("contact") or "").lower()
    email = (lead.get("email") or "").lower()
    phone = (lead.get("phone") or "").lower()

    if email or "@" in contact:
        score += 2
    if phone or any(c.isdigit() for c in contact):
        score += 2
    if lead.get("company"):
        score += 1
    if lead.get("location"):
        score += 1
    if len(details) > 50:
        score += 2
    elif len(details) > 20:
        score += 1

    urgent_words = ["urgent", "asap", "immediately", "this week", "next week", "ready", "now", "quote", "start"]
    if any(w in details for w in urgent_words):
        score += 3

    large_words = ["sq ft", "square feet", "pallet position", "5,000", "10,000", "20,000", "warehouse", "facility", "distribution"]
    if any(w in details for w in large_words):
        score += 2

    if score >= 8:
        return "\U0001f525 Hot"
    elif score >= 4:
        return "\u26a1 Warm"
    else:
        return "\u2744\ufe0f Cold"


# ── Contact Parsing ───────────────────────────────────────────────────────────

def extract_email_phone(contact: str):
    """Split a contact string into email and phone."""
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


# ── Lead Notification Email ───────────────────────────────────────────────────

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


# ── Follow-up Email to Lead ───────────────────────────────────────────────────

def send_followup_email(lead: dict):
    """Send a branded follow-up email directly to the lead."""
    email, _ = extract_email_phone(lead.get("contact", ""))
    email = lead.get("email") or email
    if not email:
        return

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
  Pacific Construction \u00b7 1574 Thornton Ave SW, Pacific, WA 98047 \u00b7 253.826.2727
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


# ── Communication Logging ─────────────────────────────────────────────────────

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
        "type":      comm_type,
        "direction": direction,
        "subject":   subject,
        "body":      body,
        "sent_by":   sent_by,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    save_lead_comms(comms)


# ── Invoice Notification ──────────────────────────────────────────────────────

def send_invoice_notification(item):
    """Notify owner/bookkeeper of new incoming invoice."""
    sender = _integ_val("GMAIL_SENDER")
    pw     = _integ_val("GMAIL_APP_PASSWORD")
    notify = _integ_val("LEAD_NOTIFY_EMAIL") or sender
    if not sender or not pw or not notify:
        return
    try:
        cfg     = load_config().get("company", {})
        company = cfg.get("name", "Pacific Construction")
        amt_str = f"${item['amount']:,.2f}" if item['amount'] else "unknown amount"
        status  = "\u2705 Job matched automatically" if item.get('job_id') else "\u26a0\ufe0f Needs job assignment"
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"\U0001f4e5 New Vendor Invoice: {item['vendor_name']} — {amt_str}"
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
            <p style="margin-top:16px;color:#666;">Log into the dashboard \u2192 Finance \u2192 Job Costs \u2192 <b>Review Queue</b> to approve or assign.</p>
        </div>"""
        msg.attach(MIMEText(html, "html"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, pw)
            server.sendmail(sender, notify, msg.as_string())
    except Exception as e:
        print(f"Invoice notification error: {e}")
