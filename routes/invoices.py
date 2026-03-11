"""
Invoices blueprint — invoice CRUD, send, preview, and invoice inbox management.

Routes:
  /dashboard/api/invoices                          → GET / POST
  /dashboard/api/invoices/<id>                     → PUT / DELETE
  /dashboard/api/invoices/<id>/send                → POST
  /dashboard/invoice/<id>                          → GET preview
  /dashboard/api/invoice-inbox                     → GET
  /dashboard/api/invoice-inbox/poll                → POST
  /dashboard/api/invoice-inbox/<id>/approve        → POST
  /dashboard/api/invoice-inbox/<id>/reject         → POST
  /dashboard/api/invoice-inbox/settings            → GET / POST
"""

import smtplib
import uuid
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from flask import Blueprint, jsonify, request

from utils.constants import GMAIL_APP_PASSWORD, GMAIL_SENDER
from utils.config import get_tax_rate, load_config, safe_float, save_config
from utils.auth import require_auth
from utils.data import (
    load_invoice_inbox, load_invoices, load_jobcosts, load_jobs,
    next_invoice_number, save_invoice_inbox, save_invoices, save_jobcosts,
)
from utils.email import log_job_comm
from utils.activity import log_activity
from utils.html_generators import _invoice_html
from utils.invoice_inbox import poll_invoice_inbox

invoices_bp = Blueprint("invoices", __name__)


# ── Invoice CRUD ──────────────────────────────────────────────────────────────

@invoices_bp.route("/dashboard/api/invoices", methods=["GET"])
@require_auth
def get_invoices():
    invoices = load_invoices()
    invoices.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return jsonify(invoices)


@invoices_bp.route("/dashboard/api/invoices", methods=["POST"])
@require_auth
def create_invoice():
    data = request.get_json() or {}
    invoices = load_invoices()
    line_items = data.get("line_items", [])
    subtotal = sum(safe_float(item.get("amount")) for item in line_items)
    apply_tax = data.get("apply_tax", False)
    tax = round(subtotal * get_tax_rate(), 2) if apply_tax else 0
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
        "tax_rate": get_tax_rate() if apply_tax else 0,
        "tax": tax,
        "total": total,
        "notes": data.get(
            "notes",
            "Payment due within 30 days. Thank you for your business.",
        ),
        "job_id": data.get("job_id", ""),
        "paid_at": None,
    }
    invoices.append(invoice)
    save_invoices(invoices)
    log_activity(
        "invoice_created",
        f"Invoice {invoice['invoice_number']} created for "
        f"{invoice['client_name']} — ${total:,.2f}",
        {"invoice_id": invoice["invoice_id"], "amount": total,
         "client": invoice["client_name"]},
    )
    return jsonify(invoice), 201


@invoices_bp.route("/dashboard/api/invoices/<inv_id>", methods=["PUT"])
@require_auth
def update_invoice(inv_id):
    data = request.get_json() or {}
    invoices = load_invoices()
    for i, inv in enumerate(invoices):
        if inv["invoice_id"] == inv_id:
            if "line_items" in data:
                line_items = data["line_items"]
                subtotal = sum(safe_float(item.get("amount")) for item in line_items)
                apply_tax = data.get("apply_tax", inv.get("apply_tax", False))
                tax = round(subtotal * get_tax_rate(), 2) if apply_tax else 0
                data["subtotal"] = round(subtotal, 2)
                data["tax"] = tax
                data["total"] = round(subtotal + tax, 2)
                data["tax_rate"] = get_tax_rate() if apply_tax else 0
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
                    log_activity(
                        "invoice_paid",
                        f"Invoice {num} marked paid — {client} (${total:,.2f})",
                        {"invoice_id": inv_id, "client": client},
                    )
                else:
                    log_activity(
                        "invoice_updated",
                        f"Invoice {num} status changed to {new_status} — {client}",
                        {"invoice_id": inv_id, "client": client},
                    )
            return jsonify(invoices[i])
    return jsonify({"error": "Not found"}), 404


@invoices_bp.route("/dashboard/api/invoices/<inv_id>", methods=["DELETE"])
@require_auth
def delete_invoice(inv_id):
    invoices = load_invoices()
    deleted = next((i for i in invoices if i["invoice_id"] == inv_id), None)
    invoices = [i for i in invoices if i["invoice_id"] != inv_id]
    save_invoices(invoices)
    if deleted:
        log_activity(
            "invoice_deleted",
            f"Invoice {deleted.get('invoice_number', '')} deleted — "
            f"{deleted.get('client_name', '')}",
            {"invoice_id": inv_id},
        )
    return jsonify({"ok": True})


# ── Invoice send / preview ────────────────────────────────────────────────────

@invoices_bp.route("/dashboard/api/invoices/<inv_id>/send", methods=["POST"])
@require_auth
def send_invoice(inv_id):
    invoices = load_invoices()
    inv = next((i for i in invoices if i["invoice_id"] == inv_id), None)
    if not inv:
        return jsonify({"error": "Not found"}), 404
    data = request.get_json(silent=True) or {}
    email = data.get("to_email") or inv.get("client_email", "")
    subject = (
        data.get("subject")
        or f"Invoice {inv['invoice_number']} — Pacific Construction"
    )
    custom_note = data.get("message", "")
    if not email:
        return jsonify({"error": "No client email on invoice"}), 400
    try:
        invoice_html = _invoice_html(inv)
        note_block = (
            '<div style="font-family:sans-serif;font-size:14px;line-height:1.6;'
            f'color:#333;padding:20px 0 28px;">{custom_note.replace(chr(10), "<br>")}'
            "</div>"
            if custom_note else ""
        )
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
        log_activity(
            "invoice_sent",
            f"Invoice {inv['invoice_number']} emailed to {email} — "
            f"{inv.get('client_name', '')} (${inv.get('total', 0):,.2f})",
            {"invoice_id": inv_id, "client": inv.get("client_name", ""),
             "email": email},
        )
        # auto-log to job comms if linked to a job
        job_id = inv.get("job_id")
        if job_id:
            log_job_comm(
                job_id, comm_type="email", direction="outbound",
                subject=f"Invoice {inv['invoice_number']} sent to {email}",
                body=f"Invoice {inv.get('invoice_number', '')} emailed to {email}.",
                sent_by="system",
            )
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@invoices_bp.route("/dashboard/invoice/<inv_id>")
def invoice_preview(inv_id):
    invoices = load_invoices()
    inv = next((i for i in invoices if i["invoice_id"] == inv_id), None)
    if not inv:
        return "Invoice not found", 404
    return _invoice_html(inv)


# ── Invoice Inbox ─────────────────────────────────────────────────────────────

@invoices_bp.route("/dashboard/api/invoice-inbox", methods=["GET"])
@require_auth
def get_invoice_inbox():
    return jsonify(load_invoice_inbox())


@invoices_bp.route("/dashboard/api/invoice-inbox/poll", methods=["POST"])
@require_auth
def trigger_invoice_poll():
    poll_invoice_inbox()
    return jsonify({"ok": True})


@invoices_bp.route("/dashboard/api/invoice-inbox/<inbox_id>/approve", methods=["POST"])
@require_auth
def approve_inbox_invoice(inbox_id):
    inbox = load_invoice_inbox()
    item = next((x for x in inbox if x.get("inbox_id") == inbox_id), None)
    if not item:
        return jsonify({"error": "Not found"}), 404
    if item.get("status") != "pending":
        return jsonify({"error": "Already processed"}), 400

    data = request.json or {}

    # Create jobcost
    costs = load_jobcosts()
    entry = {
        "cost_id": str(uuid.uuid4()),
        "job_id": data.get("job_id", item.get("matched_job_id", "")),
        "job_number": data.get("job_number", item.get("matched_job_number", "")),
        "category": data.get("category", item.get("category", "materials")),
        "description": (
            data.get("description")
            or f"Invoice #{item.get('invoice_number', '')} from {item.get('vendor', '')}"
        ),
        "vendor": item.get("vendor", ""),
        "amount": safe_float(data.get("amount", item.get("amount", 0))),
        "date": item.get("invoice_date") or datetime.now().strftime("%Y-%m-%d"),
        "receipt_ref": f"inbox:{inbox_id}",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    costs.append(entry)
    save_jobcosts(costs)

    # Mark inbox item approved
    item["status"] = "approved"
    item["approved_cost_id"] = entry["cost_id"]
    item["approved_at"] = datetime.now(timezone.utc).isoformat()
    save_invoice_inbox(inbox)

    log_activity(
        "vendor_invoice_approved",
        f"Vendor invoice #{item.get('invoice_number', '')} approved — "
        f"${entry['amount']:,.2f} ({item.get('vendor', '')})",
        {"inbox_id": inbox_id, "cost_id": entry["cost_id"]},
    )
    return jsonify({"ok": True, "cost_id": entry["cost_id"]})


@invoices_bp.route("/dashboard/api/invoice-inbox/<inbox_id>/reject", methods=["POST"])
@require_auth
def reject_inbox_invoice(inbox_id):
    inbox = load_invoice_inbox()
    item = next((x for x in inbox if x.get("inbox_id") == inbox_id), None)
    if not item:
        return jsonify({"error": "Not found"}), 404
    if item.get("status") != "pending":
        return jsonify({"error": "Already processed"}), 400
    item["status"] = "rejected"
    item["rejected_at"] = datetime.now(timezone.utc).isoformat()
    save_invoice_inbox(inbox)
    return jsonify({"ok": True})


@invoices_bp.route("/dashboard/api/invoice-inbox/settings", methods=["GET", "POST"])
@require_auth
def invoice_inbox_settings():
    if request.method == "POST":
        data = request.json or {}
        cfg = load_config()
        if "invoice_inbox" not in cfg:
            cfg["invoice_inbox"] = {}
        cfg["invoice_inbox"].update(data)
        save_config(cfg)
        return jsonify({"ok": True})
    cfg = load_config()
    return jsonify(cfg.get("invoice_inbox", {}))
