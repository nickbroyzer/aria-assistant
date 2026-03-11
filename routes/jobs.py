"""
Jobs blueprint — job CRUD, job costs, vendor invoices, followup sequences,
job comms, job files, job scheduling.

Routes:
  /dashboard/api/jobs                              → GET / POST
  /dashboard/api/jobs/<id>                         → PUT / DELETE
  /dashboard/api/jobs/<id>/followup                → GET
  /dashboard/api/jobs/<id>/files                   → GET / POST
  /dashboard/api/jobs/<id>/files/<fname>           → DELETE
  /dashboard/api/jobs/<id>/comms                   → GET / POST
  /dashboard/api/jobs/<id>/comms/<cid>             → DELETE
  /dashboard/api/jobs/<id>/send-email              → POST
  /dashboard/api/jobs/<id>/schedule                → POST
  /dashboard/job-files/<id>/<fname>                → GET (serve file)
  /dashboard/api/jobcosts                          → GET / POST
  /dashboard/api/jobcosts/<id>                     → PUT / DELETE
  /dashboard/api/vendorinvoices/<id>               → GET
  /dashboard/api/followups                         → GET
  /dashboard/api/followups/start                   → POST
  /dashboard/api/followups/<id>/pause              → POST
  /dashboard/api/followups/<id>/resume             → POST
  /dashboard/api/followups/<id>/stop               → POST
  /dashboard/api/followups/process                 → POST
  /dashboard/api/followups/send-test               → POST
"""

import os
import re
import smtplib
import uuid
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from flask import Blueprint, jsonify, request, send_from_directory

from utils.constants import DEFAULT_SETTINGS
from utils.config import _integ_val, load_config, safe_float
from utils.auth import get_current_user, load_users, require_auth
from utils.data import (
    load_followups, load_job_comms, load_jobcosts, load_jobs,
    load_vendor_invoices, next_job_number, save_followups,
    save_job_comms, save_jobcosts, save_jobs,
)
from utils.email import log_job_comm
from utils.activity import log_activity
from utils.sequences import (
    _render_template, process_due_followups,
    start_followup_sequence, stop_followup_sequence,
)
from utils.calendar import get_calendar_service, _get_calendar_id

jobs_bp = Blueprint("jobs", __name__)


# ── Jobs CRUD ─────────────────────────────────────────────────────────────────

@jobs_bp.route("/dashboard/api/jobs", methods=["GET"])
@require_auth
def get_jobs():
    jobs = load_jobs()
    jobs.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return jsonify(jobs)


@jobs_bp.route("/dashboard/api/jobs", methods=["POST"])
@require_auth
def create_job():
    data = request.get_json() or {}
    jobs = load_jobs()
    job = {
        "job_id": str(uuid.uuid4()),
        "job_number": next_job_number(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": data.get("status", "quoted"),
        "job_type": data.get("job_type", ""),
        "address": data.get("address", ""),
        "client_name": data.get("client_name", ""),
        "client_company": data.get("client_company", ""),
        "client_email": data.get("client_email", ""),
        "client_phone": data.get("client_phone", ""),
        "description": data.get("description", ""),
        "quoted_amount": safe_float(data.get("quoted_amount")),
        "actual_amount": safe_float(data.get("actual_amount")),
        "notes": data.get("notes", ""),
        "lead_id": data.get("lead_id", ""),
    }
    jobs.append(job)
    save_jobs(jobs)
    log_activity(
        "job_created",
        f"Job {job['job_number']} created — {job['job_type']} for {job['client_name']}",
        {"job_id": job["job_id"], "job_number": job["job_number"]},
    )
    return jsonify(job), 201


@jobs_bp.route("/dashboard/api/jobs/<job_id>", methods=["PUT"])
@require_auth
def update_job(job_id):
    data = request.get_json() or {}
    jobs = load_jobs()
    for j in jobs:
        if j["job_id"] == job_id:
            for k in ("status", "job_type", "address", "client_name",
                       "client_company", "client_email", "client_phone",
                       "description", "notes"):
                if k in data:
                    j[k] = data[k]
            for k in ("quoted_amount", "actual_amount"):
                if k in data:
                    j[k] = safe_float(data[k])
            save_jobs(jobs)
            return jsonify(j)
    return jsonify({"error": "Not found"}), 404


@jobs_bp.route("/dashboard/api/jobs/<job_id>", methods=["DELETE"])
@require_auth
def delete_job(job_id):
    jobs = load_jobs()
    deleted = next((j for j in jobs if j["job_id"] == job_id), None)
    jobs = [j for j in jobs if j["job_id"] != job_id]
    save_jobs(jobs)
    if deleted:
        log_activity(
            "job_deleted",
            f"Job {deleted.get('job_number', '')} deleted",
            {"job_id": job_id},
        )
    return jsonify({"ok": True})


# ── Job Costs ─────────────────────────────────────────────────────────────────

@jobs_bp.route("/dashboard/api/jobcosts", methods=["GET"])
@require_auth
def get_jobcosts():
    return jsonify(load_jobcosts())


@jobs_bp.route("/dashboard/api/jobcosts", methods=["POST"])
@require_auth
def create_jobcost():
    data = request.json or {}
    costs = load_jobcosts()
    entry = {
        "cost_id": str(uuid.uuid4()),
        "job_id": data.get("job_id", ""),
        "job_number": data.get("job_number", ""),
        "category": data.get("category", ""),
        "description": data.get("description", ""),
        "vendor": data.get("vendor", ""),
        "amount": safe_float(data.get("amount")),
        "date": data.get("date", datetime.now().strftime("%Y-%m-%d")),
        "receipt_ref": data.get("receipt_ref", ""),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    costs.append(entry)
    save_jobcosts(costs)
    return jsonify(entry), 201


@jobs_bp.route("/dashboard/api/jobcosts/<cost_id>", methods=["PUT"])
@require_auth
def update_jobcost(cost_id):
    data = request.json or {}
    costs = load_jobcosts()
    for c in costs:
        if c["cost_id"] == cost_id:
            for k in ("category", "description", "vendor", "date", "receipt_ref"):
                if k in data:
                    c[k] = data[k]
            if "amount" in data:
                c["amount"] = safe_float(data["amount"])
            save_jobcosts(costs)
            return jsonify(c)
    return jsonify({"error": "Not found"}), 404


@jobs_bp.route("/dashboard/api/jobcosts/<cost_id>", methods=["DELETE"])
@require_auth
def delete_jobcost(cost_id):
    costs = load_jobcosts()
    costs = [c for c in costs if c["cost_id"] != cost_id]
    save_jobcosts(costs)
    return jsonify({"ok": True})


# ── Vendor Invoices ───────────────────────────────────────────────────────────

@jobs_bp.route("/dashboard/api/vendorinvoices/<cost_id>", methods=["GET"])
@require_auth
def get_vendor_invoice(cost_id):
    vis = load_vendor_invoices()
    vi = next((v for v in vis if v.get("cost_id") == cost_id), None)
    if not vi:
        return jsonify({"error": "Not found"}), 404
    return jsonify(vi)


# ── Followup routes ───────────────────────────────────────────────────────────

@jobs_bp.route("/dashboard/api/followups", methods=["GET"])
@require_auth
def list_followups():
    process_due_followups()
    followups = load_followups()
    jobs = {j["job_id"]: j for j in load_jobs()}
    enriched = []
    for f in followups:
        j = jobs.get(f.get("job_id"), {})
        enriched.append({
            **f,
            "job_number": j.get("job_number", ""),
            "client_name": j.get("client_name", ""),
            "job_type": j.get("job_type", ""),
        })
    enriched.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return jsonify(enriched)


@jobs_bp.route("/dashboard/api/followups/start", methods=["POST"])
@require_auth
def api_start_followup():
    data = request.json or {}
    job_id = data.get("job_id", "")
    jobs = load_jobs()
    job = next((j for j in jobs if j["job_id"] == job_id), None)
    if not job:
        return jsonify({"ok": False, "error": "Job not found"}), 404
    followups = load_followups()
    active = next(
        (f for f in followups if f["job_id"] == job_id and f["status"] == "active"),
        None,
    )
    if active:
        return jsonify({"ok": False, "error": "Followup already active for this job"}), 400
    start_followup_sequence(job)
    return jsonify({"ok": True})


@jobs_bp.route("/dashboard/api/followups/<followup_id>/pause", methods=["POST"])
@require_auth
def pause_followup(followup_id):
    followups = load_followups()
    for f in followups:
        if f["followup_id"] == followup_id and f["status"] == "active":
            f["status"] = "paused"
            save_followups(followups)
            return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "Not found or not active"}), 404


@jobs_bp.route("/dashboard/api/followups/<followup_id>/resume", methods=["POST"])
@require_auth
def resume_followup(followup_id):
    followups = load_followups()
    for f in followups:
        if f["followup_id"] == followup_id and f["status"] == "paused":
            f["status"] = "active"
            save_followups(followups)
            return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "Not found or not paused"}), 404


@jobs_bp.route("/dashboard/api/followups/<followup_id>/stop", methods=["POST"])
@require_auth
def api_stop_followup(followup_id):
    followups = load_followups()
    rec = next((f for f in followups if f["followup_id"] == followup_id), None)
    if not rec:
        return jsonify({"ok": False, "error": "Not found"}), 404
    stop_followup_sequence(rec["job_id"], reason="manual")
    return jsonify({"ok": True})


@jobs_bp.route("/dashboard/api/followups/process", methods=["POST"])
@require_auth
def api_process_followups():
    process_due_followups()
    return jsonify({"ok": True})


@jobs_bp.route("/dashboard/api/followups/send-test", methods=["POST"])
@require_auth
def send_test_followup():
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
    users = load_users()
    owner = next((u for u in users if u.get("role") == "owner"), None)
    owner_name = owner.get("display_name", company["name"]) if owner else company["name"]

    sample_job = {
        "job_number": "JOB-2026-042",
        "job_type": "Mezzanine Fabrication",
        "address": "Kent, WA",
        "client_name": "John Smith",
        "client_email": to_email,
    }
    rendered_subject = _render_template(subject, sample_job, owner_name, company)
    rendered_body = _render_template(body_txt, sample_job, owner_name, company)

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[TEST — {label}] {rendered_subject}"
        msg["From"] = f"{company['name']} <{sender}>"
        msg["To"] = to_email

        plain = f"--- TEST EMAIL (Step {step}: {label}) ---\n\n{rendered_body}"
        html = (
            '<!DOCTYPE html><html><body style="font-family:sans-serif;color:#333;'
            'max-width:600px;margin:0 auto;padding:24px;">'
            '<div style="background:#fff3cd;border:1px solid #ffc107;border-radius:6px;'
            'padding:10px 14px;margin-bottom:20px;font-size:12px;color:#856404;">'
            f"  <strong>TEST EMAIL</strong> — Step {step}: {label}. "
            "Sample data used in place of real job values.</div>"
            '<div style="white-space:pre-line;font-size:14px;line-height:1.7;">'
            f"{rendered_body}</div>"
            '<hr style="border:none;border-top:1px solid #eee;margin:24px 0;">'
            '<div style="font-size:11px;color:#999;">'
            f"{company.get('name', '')} · {company.get('address', '')} · "
            f"{company.get('city', '')} {company.get('state', '')} "
            f"{company.get('zip', '')} · {company.get('phone', '')}</div>"
            "</body></html>"
        )
        msg.attach(MIMEText(plain, "plain"))
        msg.attach(MIMEText(html, "html"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, pw)
            server.sendmail(sender, to_email, msg.as_string())
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ── Job followup detail ───────────────────────────────────────────────────────

@jobs_bp.route("/dashboard/api/jobs/<job_id>/followup", methods=["GET"])
@require_auth
def get_job_followup(job_id):
    process_due_followups()
    followups = load_followups()
    active = next(
        (f for f in reversed(followups)
         if f["job_id"] == job_id and f["status"] in ("active", "paused")),
        None,
    )
    if not active:
        active = next(
            (f for f in reversed(followups) if f["job_id"] == job_id), None,
        )
    return jsonify(active or {})


# ── Job files ─────────────────────────────────────────────────────────────────

@jobs_bp.route("/dashboard/api/jobs/<job_id>/files", methods=["GET"])
def list_job_files(job_id):
    base = os.path.realpath("job_files")
    folder = os.path.realpath(os.path.join("job_files", job_id))
    if not folder.startswith(base + os.sep):
        return jsonify([])
    if not os.path.exists(folder):
        return jsonify([])
    files = []
    for fname in sorted(os.listdir(folder)):
        if fname.endswith(".thumb.png"):
            continue
        fpath = os.path.join(folder, fname)
        stat = os.stat(fpath)
        ext = fname.rsplit(".", 1)[-1].lower() if "." in fname else ""
        thumb_fname = fname + ".thumb.png"
        thumb_path = os.path.join(folder, thumb_fname)
        thumb_url = (
            f"/dashboard/job-files/{job_id}/{thumb_fname}"
            if os.path.exists(thumb_path) else None
        )
        files.append({
            "name": fname,
            "size": stat.st_size,
            "ext": ext,
            "is_image": ext in ("jpg", "jpeg", "png", "gif", "webp", "bmp"),
            "url": f"/dashboard/job-files/{job_id}/{fname}",
            "thumbnail_url": thumb_url,
            "uploaded": datetime.fromtimestamp(stat.st_mtime).strftime("%b %d, %Y"),
        })
    return jsonify(files)


@jobs_bp.route("/dashboard/api/jobs/<job_id>/files", methods=["POST"])
@require_auth
def upload_job_file(job_id):
    if "file" not in request.files:
        return jsonify({"error": "No file"}), 400
    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "Empty filename"}), 400
    folder = os.path.join("job_files", job_id)
    os.makedirs(folder, exist_ok=True)
    safe = re.sub(r'[^\w\.\-]', '_', f.filename)
    save_path = os.path.join(folder, safe)
    f.save(save_path)
    return jsonify({"ok": True, "name": safe})


@jobs_bp.route("/dashboard/job-files/<job_id>/<filename>")
def serve_job_file(job_id, filename):
    base = os.path.realpath("job_files")
    safe_name = re.sub(r'[^\w\.\-]', '_', filename)
    full = os.path.realpath(os.path.join("job_files", job_id, safe_name))
    if not full.startswith(base + os.sep):
        return jsonify({"error": "Not found"}), 404
    folder = os.path.dirname(full)
    return send_from_directory(folder, os.path.basename(full))


@jobs_bp.route("/dashboard/api/jobs/<job_id>/files/<filename>", methods=["DELETE"])
@require_auth
def delete_job_file(job_id, filename):
    safe = re.sub(r'[^\w\.\-]', '_', filename)
    fpath = os.path.join("job_files", job_id, safe)
    if os.path.exists(fpath):
        os.remove(fpath)
    return jsonify({"ok": True})


# ── Job comms ─────────────────────────────────────────────────────────────────

@jobs_bp.route("/dashboard/api/jobs/<job_id>/comms", methods=["GET"])
def api_job_comms_get(job_id):
    comms = load_job_comms()
    return jsonify([c for c in comms if c.get("job_id") == job_id])


@jobs_bp.route("/dashboard/api/jobs/<job_id>/comms", methods=["POST"])
@require_auth
def api_job_comms_post(job_id):
    data = request.json or {}
    comms = load_job_comms()
    user = get_current_user()
    entry = {
        "comm_id": str(uuid.uuid4()),
        "job_id": job_id,
        "type": data.get("type", "note"),
        "direction": data.get("direction", "internal"),
        "subject": data.get("subject", ""),
        "body": data.get("body", ""),
        "sent_by": user.get("display_name", "user") if user else "user",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    comms.append(entry)
    save_job_comms(comms)
    return jsonify(entry), 201


@jobs_bp.route("/dashboard/api/jobs/<job_id>/comms/<comm_id>", methods=["DELETE"])
@require_auth
def api_job_comms_delete(job_id, comm_id):
    comms = load_job_comms()
    comms = [c for c in comms if not (c.get("job_id") == job_id and c.get("comm_id") == comm_id)]
    save_job_comms(comms)
    return jsonify({"ok": True})


# ── Job email ─────────────────────────────────────────────────────────────────

@jobs_bp.route("/dashboard/api/jobs/<job_id>/send-email", methods=["POST"])
@require_auth
def api_job_send_email(job_id):
    data = request.json or {}
    to_email = data.get("to_email", "").strip()
    subject = data.get("subject", "").strip()
    body_text = data.get("body", "").strip()

    if not to_email or not subject or not body_text:
        return jsonify({"ok": False, "error": "to_email, subject, and body required"}), 400

    sender = _integ_val("GMAIL_SENDER")
    pw = _integ_val("GMAIL_APP_PASSWORD")
    if not sender or not pw:
        return jsonify({
            "ok": False,
            "error": "Gmail not configured",
        }), 400

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = to_email
        msg.attach(MIMEText(body_text, "plain"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, pw)
            server.sendmail(sender, to_email, msg.as_string())
        log_job_comm(
            job_id, comm_type="email", direction="outbound",
            subject=subject, body=body_text, sent_by="user",
        )
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ── Job scheduling ────────────────────────────────────────────────────────────

@jobs_bp.route("/dashboard/api/jobs/<job_id>/schedule", methods=["POST"])
@require_auth
def api_job_schedule(job_id):
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

        jobs = load_jobs()
        job = next((j for j in jobs if j["job_id"] == job_id), None)
        job_num = job.get("job_number", "") if job else ""
        log_activity(
            "job_appointment",
            f"Appointment scheduled for {job_num}: {title}",
            {"job_id": job_id, "event_id": created.get("id")},
        )
        log_job_comm(
            job_id, comm_type="appointment", direction="outbound",
            subject=title, body=f"Appointment: {title}", sent_by="user",
        )
        return jsonify({
            "ok": True, "event_id": created.get("id"),
            "link": created.get("htmlLink"),
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
