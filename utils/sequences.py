"""Followup and lead nurture sequence management, including background scheduler."""

import smtplib
import threading
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from utils.constants import DEFAULT_SETTINGS
from utils.config import load_config, _integ_val
from utils.data import (
    load_jobs,
    load_followups,
    save_followups,
    load_leads,
    load_lead_meta,
    save_lead_meta,
    load_lead_nurtures,
    save_lead_nurtures,
)
from utils.email import extract_email_phone, log_job_comm, log_lead_comm
from utils.activity import log_activity
from utils.auth import load_users


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
