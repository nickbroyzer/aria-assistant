import anthropic
"""
Dashboard blueprint — auth, users, settings, stats, data export, comp PIN.

Routes:
  /dashboard                          → dashboard page
  /dashboard/api/login                → POST login
  /dashboard/api/logout               → POST logout
  /dashboard/api/me                   → GET current user
  /dashboard/api/users                → GET / POST
  /dashboard/api/users/<id>           → PUT / DELETE
  /dashboard/api/stats                → GET lead stats
  /dashboard/api/appointments         → GET calendar appointments
  /dashboard/api/activity             → GET activity feed
  /dashboard/api/settings/<section>   → GET / POST
  /dashboard/api/settings/logo        → POST upload
  /dashboard/api/settings/company-public
  /dashboard/api/settings/integrations
  /dashboard/api/settings/integration → POST save integration creds
  /dashboard/api/settings/change-master-password
  /dashboard/api/settings/set-dev-password
  /dashboard/api/verify-dev-access
  /dashboard/api/verify-comp-pin
  /dashboard/api/change-comp-pin
  /dashboard/api/data/export
  /dashboard/api/data/summary
"""

import os
import zipfile
import io as _io
from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, render_template, request, send_file, session
from werkzeug.security import generate_password_hash, check_password_hash

from utils.constants import (
    CALENDAR_TOKEN, DEFAULT_SETTINGS, LEADS_FILE, MASTER_PASSWORD,
    SETTINGS_SECTIONS,
)
from utils.config import (
    _check_dev_password, _integ_val, load_config, save_config, get_tax_rate,
)
from utils.auth import (
    get_current_user, load_users, require_auth, require_owner, save_users,
)
from utils.data import (
    load_nurtures,
    load_invoices, load_jobs, load_leads, load_payroll, load_people,
)
from utils.activity import load_activity, log_activity
from utils.calendar import get_calendar_service, _get_calendar_id

dashboard_bp = Blueprint("dashboard", __name__)

ALL_PERMISSIONS = {
    "leads": True, "appointments": True, "jobs": True,
    "invoices": True, "jobcosts": True, "people": True,
    "payroll": True, "settings": True,
}


# ── Dashboard page ────────────────────────────────────────────────────────────

@dashboard_bp.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")


# ── Auth routes ───────────────────────────────────────────────────────────────

@dashboard_bp.route("/dashboard/api/login", methods=["POST"])
def dashboard_login():
    data = request.json or {}
    username = data.get("username", "").strip().lower()
    password = data.get("password", "")

    users = load_users()
    user = next(
        (u for u in users
         if u.get("username", "").lower() == username and u.get("active", True)),
        None,
    )

    if user and check_password_hash(user.get("password_hash", ""), password):
        session["user_id"] = user["user_id"]
        user["last_login"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        save_users(users)
        safe = {
            k: user[k]
            for k in ("user_id", "username", "display_name", "role", "permissions")
            if k in user
        }
        return jsonify({"ok": True, "user": safe})

    # Legacy fallback — single password for owner
    if not username and password == MASTER_PASSWORD:
        session["user_id"] = "owner-jay"
        return jsonify({
            "ok": True,
            "user": {"role": "owner", "display_name": "Jay", "permissions": {}},
        })

    return jsonify({"ok": False, "error": "Invalid username or password"}), 401


@dashboard_bp.route("/dashboard/api/logout", methods=["POST"])
def dashboard_logout():
    session.clear()
    return jsonify({"ok": True})


@dashboard_bp.route("/dashboard/api/me", methods=["GET"])
def dashboard_me():
    user = get_current_user()
    if not user:
        if session.get("user_id") == "owner-jay":
            return jsonify({
                "ok": True,
                "user": {"role": "owner", "display_name": "Jay", "permissions": {}},
            })
        return jsonify({"ok": False}), 401
    safe = {
        k: user[k]
        for k in ("user_id", "username", "display_name", "role", "permissions")
        if k in user
    }
    return jsonify({"ok": True, "user": safe})


# ── Users management ──────────────────────────────────────────────────────────

@dashboard_bp.route("/dashboard/api/users", methods=["GET"])
def list_users():
    users = load_users()
    result = []
    for u in users:
        safe = {k: u[k] for k in u if k != "password_hash"}
        if u.get("role") == "owner":
            safe["permissions"] = ALL_PERMISSIONS.copy()
        result.append(safe)
    return jsonify(result)


@dashboard_bp.route("/dashboard/api/users", methods=["POST"])
def create_user():
    import uuid
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

    default_perms = {
        "leads": True, "appointments": True, "jobs": True,
        "invoices": True, "jobcosts": True, "people": True,
        "payroll": False, "settings": False,
    }
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


@dashboard_bp.route("/dashboard/api/users/<user_id>", methods=["PUT"])
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
        user["permissions"] = {**user.get("permissions", {}), **data["permissions"]}

    if data.get("password"):
        if len(data["password"]) < 6:
            return jsonify({"error": "Password must be at least 6 characters"}), 400
        user["password_hash"] = generate_password_hash(data["password"])

    save_users(users)
    safe = {k: user[k] for k in user if k != "password_hash"}
    return jsonify(safe)


@dashboard_bp.route("/dashboard/api/users/<user_id>", methods=["DELETE"])
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


# ── Stats & activity ──────────────────────────────────────────────────────────

@dashboard_bp.route("/dashboard/api/stats")
def dashboard_stats():
    leads = load_leads()
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    total = len(leads)
    hot = sum(1 for l in leads if "Hot" in l.get("score", ""))
    warm = sum(1 for l in leads if "Warm" in l.get("score", ""))
    cold = sum(1 for l in leads if "Cold" in l.get("score", ""))
    this_week = sum(
        1 for l in leads if l.get("timestamp", "") >= week_ago.isoformat()
    )
    return jsonify({
        "total": total, "hot": hot, "warm": warm, "cold": cold,
        "this_week": this_week,
    })


@dashboard_bp.route("/dashboard/api/activity")
def api_activity():
    return jsonify(load_activity(50))


@dashboard_bp.route("/dashboard/api/appointments")
def dashboard_appointments():
    try:
        service = get_calendar_service()
        now = datetime.now(timezone.utc)
        PDT = timezone(timedelta(hours=-7))
        now_pacific = datetime.now(PDT)
        today_min = now_pacific.replace(hour=0, minute=0, second=0, microsecond=0)
        end = now + timedelta(days=90)
        result = service.events().list(
            calendarId=_get_calendar_id(),
            timeMin=today_min.isoformat(),
            timeMax=end.isoformat(),
            singleEvents=True,
            orderBy="startTime",
        ).execute()
        events = []
        for e in result.get("items", []):
            start = e.get("start", {}).get("dateTime") or e.get("start", {}).get("date", "")
            end_ = e.get("end", {}).get("dateTime") or e.get("end", {}).get("date", "")
            events.append({
                "id": e.get("id"),
                "title": e.get("summary", "Appointment"),
                "start": start,
                "end": end_,
                "description": e.get("description", ""),
                "link": e.get("htmlLink", ""),
            })
        return jsonify(events)
    except Exception:
        return jsonify([])




@dashboard_bp.route("/dashboard/api/lead-nurtures")
def dashboard_lead_nurtures():
    try:
        nurtures = load_nurtures()
        return jsonify(nurtures)
    except Exception as e:
        return jsonify([])


@dashboard_bp.route("/dashboard/api/ash-analysis", methods=["POST"])
def ash_sales_analysis():
    try:
        data = request.json or {}
        prompt = data.get("prompt", "")
        if not prompt:
            return jsonify({"error": "No prompt provided"}), 400
        import json as _json
        with open('config.json') as _f:
            _cfg = _json.load(_f)
        _key = _cfg.get('anthropic_api_key', '')
        client = anthropic.Anthropic(api_key=_key)
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            system="You are Ash, a sharp business analyst AI for Pacific Construction, a warehouse installation company in Pacific, WA. Give direct, specific, actionable sales insights. Be concise — 3 bullet points max. No markdown symbols, no asterisks, no bullet dashes. Just plain numbered insights.",
            messages=[{"role": "user", "content": prompt}]
        )
        return jsonify({"text": message.content[0].text})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Settings ──────────────────────────────────────────────────────────────────

@dashboard_bp.route("/dashboard/api/settings/change-master-password", methods=["POST"])
def change_master_password():
    data = request.json or {}
    current = data.get("current_password", "")
    new_pw = data.get("new_password", "").strip()

    users = load_users()
    owner = next((u for u in users if u.get("role") == "owner"), None)

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


@dashboard_bp.route("/dashboard/api/settings/<section>", methods=["GET"])
def get_settings_section(section):
    if section not in SETTINGS_SECTIONS:
        return jsonify({"error": "Unknown section"}), 404
    cfg = load_config()
    defaults = DEFAULT_SETTINGS.get(section, {})
    merged = {**defaults, **cfg.get(section, {})}
    return jsonify(merged)


@dashboard_bp.route("/dashboard/api/settings/<section>", methods=["POST"])
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


@dashboard_bp.route("/dashboard/api/settings/logo", methods=["POST"])
def upload_logo():
    if "logo" not in request.files:
        return jsonify({"error": "No file"}), 400
    f = request.files["logo"]
    if not f.filename:
        return jsonify({"error": "No file selected"}), 400
    ext = f.filename.rsplit(".", 1)[-1].lower()
    if ext not in ("png", "jpg", "jpeg", "gif", "webp", "svg"):
        return jsonify({"error": "Invalid file type"}), 400
    static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
    os.makedirs(static_dir, exist_ok=True)
    logo_path = os.path.join(static_dir, f"company_logo.{ext}")
    f.save(logo_path)
    cfg = load_config()
    cfg["logo_url"] = f"/static/company_logo.{ext}"
    save_config(cfg)
    return jsonify({"ok": True, "url": f"/static/company_logo.{ext}"})


@dashboard_bp.route("/dashboard/api/settings/company-public", methods=["GET"])
def company_public():
    cfg = load_config()
    co = {**DEFAULT_SETTINGS["company"], **cfg.get("company", {})}
    return jsonify({
        k: co.get(k, "")
        for k in ("name", "address", "city", "state", "zip", "phone",
                   "email", "website", "tax_rate", "logo_url")
    })


@dashboard_bp.route("/dashboard/api/settings/integrations", methods=["GET"])
def settings_integrations():
    cal_connected = os.path.exists(CALENDAR_TOKEN)
    gmail_sender = _integ_val("GMAIL_SENDER")
    gmail_pw = _integ_val("GMAIL_APP_PASSWORD")
    twilio_sid = _integ_val("TWILIO_ACCOUNT_SID")
    twilio_token = _integ_val("TWILIO_AUTH_TOKEN")
    sheets_hook = _integ_val("SHEETS_WEBHOOK")
    inbox_email = _integ_val("INVOICE_INBOX_EMAIL")
    inbox_pw = _integ_val("INVOICE_INBOX_PASSWORD")
    return jsonify({
        "google_calendar":     cal_connected,
        "calendar_id":         _integ_val("CALENDAR_ID"),
        "calendar_email":      _integ_val("CALENDAR_EMAIL"),
        "gmail":               bool(gmail_sender) and bool(gmail_pw),
        "gmail_sender":        gmail_sender,
        "twilio":              bool(twilio_sid) and bool(twilio_token),
        "twilio_phone":        _integ_val("TWILIO_FROM"),
        "lead_notify_email":   _integ_val("LEAD_NOTIFY_EMAIL"),
        "sheets_webhook":      bool(sheets_hook),
        "invoice_inbox":       bool(inbox_email) and bool(inbox_pw),
        "invoice_inbox_email": inbox_email,
    })


@dashboard_bp.route("/dashboard/api/verify-dev-access", methods=["POST"])
def verify_dev_access():
    data = request.json or {}
    if _check_dev_password(data.get("password", "")):
        session["dev_unlocked"] = True
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "Incorrect developer password"}), 401


@dashboard_bp.route("/dashboard/api/settings/set-dev-password", methods=["POST"])
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


@dashboard_bp.route("/dashboard/api/settings/integration", methods=["POST"])
def save_integration():
    if not session.get("dev_unlocked"):
        return jsonify({"ok": False, "error": "Developer access required"}), 403
    data = request.json or {}
    allowed_fields = {
        "GMAIL_SENDER", "GMAIL_APP_PASSWORD", "LEAD_NOTIFY_EMAIL",
        "TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_FROM",
        "SHEETS_WEBHOOK", "CALENDAR_ID", "CALENDAR_EMAIL",
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


# ── Data export / summary ────────────────────────────────────────────────────

@dashboard_bp.route("/dashboard/api/data/export", methods=["GET"])
def export_data():
    buf = _io.BytesIO()
    ts = datetime.now().strftime("%Y%m%d-%H%M")
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for fname in ["jobs.json", "payroll.json", "people.json",
                       "invoices.json", "config.json", LEADS_FILE]:
            if os.path.exists(fname):
                zf.write(fname)
    buf.seek(0)
    return send_file(buf, mimetype="application/zip", as_attachment=True,
                     download_name=f"pacific-construction-backup-{ts}.zip")


@dashboard_bp.route("/dashboard/api/data/summary", methods=["GET"])
def data_summary():
    jobs = load_jobs()
    invoices = load_invoices()
    people = load_people()
    payroll = load_payroll()
    leads_count = len(load_leads())
    return jsonify({
        "jobs": len(jobs), "invoices": len(invoices),
        "people": len(people), "payroll": len(payroll),
        "leads": leads_count,
    })


# ── Compensation PIN ──────────────────────────────────────────────────────────

@dashboard_bp.route("/dashboard/api/verify-comp-pin", methods=["POST"])
def verify_comp_pin():
    data = request.json or {}
    cfg = load_config()
    if data.get("pin") == cfg.get("comp_pin", "1234"):
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "Incorrect PIN"}), 401


@dashboard_bp.route("/dashboard/api/change-comp-pin", methods=["POST"])
def change_comp_pin():
    data = request.json or {}
    if data.get("master_password") != MASTER_PASSWORD:
        return jsonify({"ok": False, "error": "Incorrect master password"}), 403
    new_pin = str(data.get("new_pin", "")).strip()
    if not new_pin.isdigit() or len(new_pin) != 4:
        return jsonify({"ok": False, "error": "PIN must be exactly 4 digits"}), 400
    cfg = load_config()
    cfg["comp_pin"] = new_pin
    cfg["comp_pin_changed"] = datetime.now().strftime("%Y-%m-%d")
    save_config(cfg)
    return jsonify({"ok": True})
