"""
Ash scanner blueprint — Gmail inbox scanning for supplier-related emails.

Routes:
  /api/ash/scan                   → GET scan inbox for supplier emails
  /api/ash/status                 → GET Gmail connection status
  /oauth/gmail/start              → GET redirect to Gmail OAuth flow
  /oauth/gmail/callback           → GET handle OAuth callback
  /api/ash/bookkeeping            → GET bookkeeping demo items
  /api/retell/webhook             → POST Retell AI call webhook (no auth)
"""

from datetime import date, datetime, timedelta, timezone

from flask import Blueprint, jsonify, redirect, request, session, url_for

from utils.auth import require_auth
from utils.gmail_auth import (
    is_gmail_connected, gmail_auth_url, gmail_exchange_code,
    get_gmail_account_info,
)
from utils.ash_scanner import scan_inbox
from utils.retell_client import get_recent_calls, get_call_detail
from utils.suppliers_db import insert_retell_call, get_retell_calls, save_sms, get_sms_messages


ash_bp = Blueprint("ash", __name__)


# ── Retell Webhook ────────────────────────────────────────────────────────────

@ash_bp.route("/api/retell/webhook", methods=["POST"])
def api_retell_webhook():
    """
    Receive Retell AI call webhooks. No auth — called externally by Retell.
    Only processes event == "call_analyzed"; returns 200 for all other events.
    Deduplicates by call_id.
    """
    data = request.get_json(silent=True) or {}
    event = data.get("event", "")

    if event != "call_analyzed":
        return jsonify({"status": "ok"})

    call = data.get("call", {})
    call_id = call.get("call_id")
    if not call_id:
        return jsonify({"status": "ok"})

    insert_retell_call({
        "call_id": call_id,
        "from_number": call.get("from_number"),
        "direction": call.get("direction"),
        "start_timestamp": call.get("start_timestamp"),
        "end_timestamp": call.get("end_timestamp"),
        "transcript": call.get("transcript"),
        "disconnection_reason": call.get("disconnection_reason"),
    })

    return jsonify({"status": "ok"})


@ash_bp.route("/webhook/twilio/sms", methods=["POST"])
def webhook_twilio_sms():
    """
    Receive inbound SMS via Twilio webhook. No auth — called externally by Twilio.
    Stores the message and returns empty TwiML (no auto-reply).
    """
    from_number = request.form.get("From", "")
    to_number = request.form.get("To", "")
    body = request.form.get("Body", "")

    if from_number and body:
        save_sms(from_number, to_number, body, direction="inbound")

    return '<Response></Response>', 200, {"Content-Type": "application/xml"}


@ash_bp.route("/api/ash/scan", methods=["GET"])
@require_auth
def api_ash_scan():
    """
    Scan Gmail inbox for supplier-related emails.

    Query parameters:
        max_results (int, optional): Max emails to return. Default 50.
        days_back (int, optional): Days back to search. Default 30.

    Returns:
        JSON: List of scanned email results with supplier/order matches.
    """
    max_results = request.args.get("max_results", default=50, type=int)
    days_back = request.args.get("days_back", default=30, type=int)

    results = scan_inbox(max_results=max_results, days_back=days_back)
    return jsonify({"results": results, "count": len(results)})


@ash_bp.route("/api/ash/status", methods=["GET"])
@require_auth
def api_ash_status():
    """
    Get Gmail OAuth connection status.

    Returns:
        JSON: { "connected": bool, "email": str or null }
    """
    connected = is_gmail_connected()
    email = None

    if connected:
        email = get_gmail_account_info()

    return jsonify({
        "connected": connected,
        "email": email,
    })


@ash_bp.route("/oauth/gmail/start", methods=["GET"])
def oauth_gmail_start():
    """
    Redirect to Gmail OAuth authorization flow.

    Returns:
        Redirect: To Google's OAuth consent screen.
    """
    try:
        auth_url, state = gmail_auth_url()
        session["gmail_oauth_state"] = state
        return redirect(auth_url)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@ash_bp.route("/oauth/gmail/callback", methods=["GET"])
def oauth_gmail_callback():
    """
    Handle OAuth callback from Google.

    Exchanges the authorization code for credentials and saves the token.

    Returns:
        Redirect: Back to the dashboard on success, or error response.
    """
    code = request.args.get("code")
    state = request.args.get("state")
    if not code:
        return jsonify({"error": "No authorization code provided"}), 400

    try:
        gmail_exchange_code(code, state)
        return redirect("/dashboard")
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Ash Tab Routes ─────────────────────────────────────────────────────────────

def _format_retell_timestamp(ts):
    if not ts:
        return ""
    try:
        from datetime import datetime, timezone, timedelta
        if isinstance(ts, (int, float)) and ts > 1e10:
            ts = ts / 1000
        dt = datetime.fromtimestamp(float(ts), tz=timezone.utc)
        # Pacific time: UTC-8 standard, UTC-7 daylight
        import time
        is_dst = time.daylight and time.localtime(float(ts)).tm_isdst > 0
        offset = timedelta(hours=-7 if is_dst else -8)
        dt_pacific = dt.astimezone(timezone(offset))
        return dt_pacific.isoformat()
    except Exception:
        return str(ts)


def _today_str():
    return date.today().isoformat()


def _yesterday_str():
    return (date.today() - timedelta(days=1)).isoformat()


def _build_inbox_demo():
    t = _today_str()
    y = _yesterday_str()
    return [
        # ── Today (15 items) ──
        {"id": "item-001", "type": "call", "sender": "Brian Holloway", "sender_contact": "+1 (253) 847-2291",
         "summary": "Inquired about pallet racking installation for a 12,000 sq ft warehouse in Tacoma. Has existing concrete anchoring. Wants quote by end of week.",
         "outcome": "lead_created", "quality_score": 92, "timestamp": f"{t}T09:14:00-07:00", "duration_seconds": 187, "lead_id": "lead-088"},
        {"id": "item-002", "type": "email", "sender": "Sandra Kowalski", "sender_contact": "skowalski@cascadelogistics.com",
         "summary": "Requested quote for wire decking on 80 existing pallet rack bays. Attached floor plan. Needs install within 30 days.",
         "outcome": "lead_created", "quality_score": 87, "timestamp": f"{t}T08:41:00-07:00", "duration_seconds": None, "lead_id": "lead-087"},
        {"id": "item-003", "type": "call", "sender": "Unknown Caller", "sender_contact": "+1 (206) 555-0193",
         "summary": "Asked about residential garage shelving. Explained Pacific Construction is commercial only. Referred to Home Depot.",
         "outcome": "not_qualified", "quality_score": 12, "timestamp": f"{t}T08:03:00-07:00", "duration_seconds": 94, "lead_id": None},
        {"id": "item-011", "type": "call", "sender": "Rachel Dunn", "sender_contact": "+1 (253) 602-8814",
         "summary": "Needs drive-in racking for cold storage expansion at Kent facility. 6,000 sq ft. Timeline: 45 days.",
         "outcome": "lead_created", "quality_score": 91, "timestamp": f"{t}T10:22:00-07:00", "duration_seconds": 245, "lead_id": "lead-089"},
        {"id": "item-012", "type": "email", "sender": "Northwest Steel Supply", "sender_contact": "sales@nwsteel.com",
         "summary": "PO-2026-048 shipped — 24 upright frames, 96 beams. Tracking number attached. ETA Wednesday.",
         "outcome": "invoice_logged", "quality_score": 80, "timestamp": f"{t}T10:05:00-07:00", "duration_seconds": None, "lead_id": None},
        {"id": "item-013", "type": "sms", "sender": "Luis Medina", "sender_contact": "+1 (425) 330-7762",
         "summary": "Texted photos of existing carton flow rack needing replacement. Wants site visit this week.",
         "outcome": "lead_created", "quality_score": 76, "timestamp": f"{t}T09:48:00-07:00", "duration_seconds": None, "lead_id": "lead-090"},
        {"id": "item-014", "type": "call", "sender": "Puget Sound Brewing", "sender_contact": "+1 (206) 441-3300",
         "summary": "Brewery needs keg racking system for new taproom warehouse. ~2,000 sq ft. Budget flexible.",
         "outcome": "lead_created", "quality_score": 84, "timestamp": f"{t}T11:15:00-07:00", "duration_seconds": 198, "lead_id": "lead-091"},
        {"id": "item-015", "type": "email", "sender": "Valerie Chang", "sender_contact": "vchang@premierpaper.com",
         "summary": "Following up on quote 2026-Q-022 for Premier Paper. Approved with minor revision — wants to remove one bay.",
         "outcome": "lead_created", "quality_score": 94, "timestamp": f"{t}T11:02:00-07:00", "duration_seconds": None, "lead_id": "lead-092"},
        {"id": "item-016", "type": "call", "sender": "Robo-call", "sender_contact": "+1 (800) 555-0101",
         "summary": "Automated warranty extension call. Blocked.",
         "outcome": "not_qualified", "quality_score": 1, "timestamp": f"{t}T07:45:00-07:00", "duration_seconds": 8, "lead_id": None},
        {"id": "item-017", "type": "sms", "sender": "Jake Noonan", "sender_contact": "+1 (360) 910-2245",
         "summary": "Confirming crew arrival at Tran Distribution job site tomorrow 7 AM. Three installers.",
         "outcome": "forwarded", "quality_score": 65, "timestamp": f"{t}T12:30:00-07:00", "duration_seconds": None, "lead_id": None},
        {"id": "item-018", "type": "email", "sender": "Unarco Industries", "sender_contact": "ar@unarco.com",
         "summary": "Payment reminder for INV-U-2026-088, $6,240.00 — due in 3 days. Please remit.",
         "outcome": "invoice_logged", "quality_score": 72, "timestamp": f"{t}T07:30:00-07:00", "duration_seconds": None, "lead_id": None},
        {"id": "item-019", "type": "call", "sender": "David Park", "sender_contact": "+1 (425) 778-6601",
         "summary": "Owns auto parts distributor in Everett. Needs pallet racking for 8,000 sq ft. Currently using floor stacking.",
         "outcome": "lead_created", "quality_score": 88, "timestamp": f"{t}T13:10:00-07:00", "duration_seconds": 276, "lead_id": "lead-093"},
        {"id": "item-020", "type": "email", "sender": "Cascade Logistics", "sender_contact": "ops@cascadelogistics.com",
         "summary": "Requesting add-on quote for 20 additional wire deck panels to existing order. Same specs.",
         "outcome": "lead_created", "quality_score": 82, "timestamp": f"{t}T13:45:00-07:00", "duration_seconds": None, "lead_id": "lead-094"},
        {"id": "item-021", "type": "call", "sender": "Maria Santana", "sender_contact": "+1 (253) 215-9934",
         "summary": "Ash answered — caller looking for shelving for a food bank. Non-profit discount inquiry. Forwarded to Jay.",
         "outcome": "forwarded", "quality_score": 58, "timestamp": f"{t}T14:20:00-07:00", "duration_seconds": 142, "lead_id": None},
        {"id": "item-022", "type": "sms", "sender": "Tony Marchetti", "sender_contact": "+1 (206) 444-9921",
         "summary": "Confirmed Thursday site visit for mezzanine platform measurement. Will have forklift access.",
         "outcome": "forwarded", "quality_score": 60, "timestamp": f"{t}T14:55:00-07:00", "duration_seconds": None, "lead_id": None},
        # ── Yesterday (15 items) ──
        {"id": "item-004", "type": "sms", "sender": "Derek Tran", "sender_contact": "+1 (425) 918-4477",
         "summary": "Texted asking for status update on quote for Tran Distribution. Forwarded to Jay for follow-up.",
         "outcome": "forwarded", "quality_score": 55, "timestamp": f"{y}T16:22:00-07:00", "duration_seconds": None, "lead_id": None},
        {"id": "item-005", "type": "call", "sender": "Marcus Webb", "sender_contact": "+1 (360) 204-8832",
         "summary": "Needs cantilever racking for lumber storage at Auburn facility. 3,500 sq ft area. Budget around $18,000. Ready to move forward.",
         "outcome": "lead_created", "quality_score": 95, "timestamp": f"{y}T14:55:00-07:00", "duration_seconds": 312, "lead_id": "lead-086"},
        {"id": "item-006", "type": "email", "sender": "PFP Freight Systems", "sender_contact": "orders@pfpfreight.com",
         "summary": "Supplier order confirmation for upright frames PO-2026-041. Estimated delivery March 19.",
         "outcome": "invoice_logged", "quality_score": 78, "timestamp": f"{y}T11:30:00-07:00", "duration_seconds": None, "lead_id": None},
        {"id": "item-023", "type": "call", "sender": "Gina Reyes", "sender_contact": "+1 (253) 771-0045",
         "summary": "Follow-up on quote 2026-Q-019 for Reyes Cold Storage. Approved the quote, wants to schedule install for April 7.",
         "outcome": "lead_created", "quality_score": 98, "timestamp": f"{y}T15:18:00-07:00", "duration_seconds": 228, "lead_id": "lead-085"},
        {"id": "item-024", "type": "sms", "sender": "Tony Marchetti", "sender_contact": "+1 (206) 444-9921",
         "summary": "Asked if Pacific Construction handles mezzanine platforms. Ash confirmed yes and offered to schedule a site visit.",
         "outcome": "lead_created", "quality_score": 71, "timestamp": f"{y}T10:44:00-07:00", "duration_seconds": None, "lead_id": "lead-084"},
        {"id": "item-025", "type": "call", "sender": "Auto Insurance Spam", "sender_contact": "+1 (888) 201-5544",
         "summary": "Automated spam call. No action taken.",
         "outcome": "not_qualified", "quality_score": 2, "timestamp": f"{y}T09:05:00-07:00", "duration_seconds": 11, "lead_id": None},
        {"id": "item-026", "type": "email", "sender": "Kim Wholesale Group", "sender_contact": "rkim@kimwholesale.com",
         "summary": "Invoice dispute on INV-2026-010. Claims wire decking quantity billed is incorrect. Flagged for Jay review.",
         "outcome": "forwarded", "quality_score": 60, "timestamp": f"{y}T13:55:00-07:00", "duration_seconds": None, "lead_id": None},
        {"id": "item-027", "type": "call", "sender": "Steve Nakamura", "sender_contact": "+1 (206) 887-3340",
         "summary": "Runs e-commerce fulfillment center in Renton. Needs pick module shelving for 4,200 sq ft. High priority.",
         "outcome": "lead_created", "quality_score": 90, "timestamp": f"{y}T09:30:00-07:00", "duration_seconds": 205, "lead_id": "lead-095"},
        {"id": "item-028", "type": "email", "sender": "Ridgeline Fasteners", "sender_contact": "billing@ridgelinefasteners.com",
         "summary": "Invoice INV-RF-1187 attached for anchor bolt order. $1,890.00 net 30.",
         "outcome": "invoice_logged", "quality_score": 75, "timestamp": f"{y}T08:15:00-07:00", "duration_seconds": None, "lead_id": None},
        {"id": "item-029", "type": "call", "sender": "Unknown Caller", "sender_contact": "+1 (360) 555-0072",
         "summary": "Wrong number — looking for a dentist office. Call lasted 12 seconds.",
         "outcome": "not_qualified", "quality_score": 3, "timestamp": f"{y}T08:02:00-07:00", "duration_seconds": 12, "lead_id": None},
        {"id": "item-030", "type": "sms", "sender": "Ashley (Staff)", "sender_contact": "+1 (253) 100-0002",
         "summary": "Sent photo of damaged beam at Reyes Cold Storage job site. Replacement needed before install.",
         "outcome": "forwarded", "quality_score": 68, "timestamp": f"{y}T12:10:00-07:00", "duration_seconds": None, "lead_id": None},
        {"id": "item-031", "type": "email", "sender": "Olympic Steel Rack", "sender_contact": "orders@olympicsteelrack.com",
         "summary": "Backordered items on PO-2026-039 now available. Shipping this week. Updated ETA attached.",
         "outcome": "invoice_logged", "quality_score": 77, "timestamp": f"{y}T10:00:00-07:00", "duration_seconds": None, "lead_id": None},
        {"id": "item-032", "type": "call", "sender": "Priya Sharma", "sender_contact": "+1 (425) 662-1190",
         "summary": "Pharmacy distribution center needs narrow-aisle racking. 5,500 sq ft. Seismic zone compliance required.",
         "outcome": "lead_created", "quality_score": 86, "timestamp": f"{y}T11:45:00-07:00", "duration_seconds": 267, "lead_id": "lead-096"},
        {"id": "item-033", "type": "email", "sender": "Jay (Owner)", "sender_contact": "jay@pacificconstruction.com",
         "summary": "Internal — forwarded revised floor plan from Apex 3PL for Kent facility quote update.",
         "outcome": "forwarded", "quality_score": 50, "timestamp": f"{y}T14:05:00-07:00", "duration_seconds": None, "lead_id": None},
        {"id": "item-034", "type": "call", "sender": "Emerald City Distributors", "sender_contact": "+1 (206) 330-8800",
         "summary": "New inquiry — needs pushback racking for beverage warehouse. 10,000 sq ft. Budget $35K. Wants site visit.",
         "outcome": "lead_created", "quality_score": 93, "timestamp": f"{y}T15:40:00-07:00", "duration_seconds": 290, "lead_id": "lead-097"},
    ]


def _build_bookkeeping_demo():
    t = _today_str()
    y = _yesterday_str()
    return [
        {"id": "bk-001", "category": "payable", "vendor": "PFP Freight Systems", "description": "PO-2026-041 upright frames delivery",
         "amount": 8420.00, "status": "pending", "due_date": f"{t}", "timestamp": f"{t}T09:00:00-07:00"},
        {"id": "bk-002", "category": "payable", "vendor": "Unarco Industries", "description": "INV-U-2026-088 beam & connector order",
         "amount": 6240.00, "status": "overdue", "due_date": f"{y}", "timestamp": f"{t}T07:30:00-07:00"},
        {"id": "bk-003", "category": "receivable", "vendor": "Reyes Cold Storage", "description": "Quote 2026-Q-019 deposit — 50% upfront",
         "amount": 14200.00, "status": "pending", "due_date": f"{t}", "timestamp": f"{t}T10:15:00-07:00"},
        {"id": "bk-004", "category": "payable", "vendor": "Northwest Steel Supply", "description": "PO-2026-048 frames & beams shipment",
         "amount": 5680.00, "status": "pending", "due_date": f"{t}", "timestamp": f"{t}T10:05:00-07:00"},
        {"id": "bk-005", "category": "expense", "vendor": "Home Depot Pro", "description": "Concrete anchors & hardware — Tacoma job prep",
         "amount": 342.50, "status": "paid", "due_date": f"{y}", "timestamp": f"{t}T08:20:00-07:00"},
        {"id": "bk-006", "category": "receivable", "vendor": "Cascade Logistics", "description": "Wire decking install — progress payment #2",
         "amount": 9800.00, "status": "invoiced", "due_date": f"{t}", "timestamp": f"{t}T11:00:00-07:00"},
        {"id": "bk-007", "category": "payable", "vendor": "Ridgeline Fasteners", "description": "INV-RF-1187 anchor bolt order",
         "amount": 1890.00, "status": "pending", "due_date": f"{y}", "timestamp": f"{y}T08:15:00-07:00"},
        {"id": "bk-008", "category": "expense", "vendor": "Sunbelt Rentals", "description": "Forklift rental — 1 week, Auburn job site",
         "amount": 1150.00, "status": "paid", "due_date": f"{y}", "timestamp": f"{y}T09:00:00-07:00"},
        {"id": "bk-009", "category": "receivable", "vendor": "Tran Distribution", "description": "Final payment — cantilever rack install complete",
         "amount": 11500.00, "status": "paid", "due_date": f"{y}", "timestamp": f"{y}T10:30:00-07:00"},
        {"id": "bk-010", "category": "payable", "vendor": "Olympic Steel Rack", "description": "PO-2026-039 backorder shipment",
         "amount": 4320.00, "status": "pending", "due_date": f"{t}", "timestamp": f"{y}T10:00:00-07:00"},
        {"id": "bk-011", "category": "expense", "vendor": "WA State L&I", "description": "Quarterly workers comp premium — Q1 2026",
         "amount": 2840.00, "status": "due_soon", "due_date": f"{t}", "timestamp": f"{y}T07:00:00-07:00"},
        {"id": "bk-012", "category": "receivable", "vendor": "Premier Paper", "description": "Quote 2026-Q-022 deposit — revised scope",
         "amount": 7600.00, "status": "paid", "due_date": f"{t}", "timestamp": f"{t}T11:02:00-07:00"},
        {"id": "bk-013", "category": "payable", "vendor": "Fastenal", "description": "Monthly fastener & safety supply order",
         "amount": 478.25, "status": "paid", "due_date": f"{y}", "timestamp": f"{y}T14:00:00-07:00"},
        {"id": "bk-014", "category": "expense", "vendor": "Verizon Business", "description": "Monthly cell phone plan — 4 lines",
         "amount": 289.00, "status": "paid", "due_date": f"{y}", "timestamp": f"{y}T06:00:00-07:00"},
        {"id": "bk-015", "category": "receivable", "vendor": "Puget Sound Brewing", "description": "Keg racking system — signed estimate, awaiting deposit",
         "amount": 5400.00, "status": "pending", "due_date": f"{t}", "timestamp": f"{t}T11:15:00-07:00"},
    ]

def _build_activity_demo():
    t = _today_str()
    y = _yesterday_str()
    return [
        # ── Today (13 items) ──
        {"id": "act-001", "timestamp": f"{t}T09:15:00-07:00", "action_type": "lead_created",
         "description": "Created lead — Brian Holloway, Tacoma warehouse racking inquiry. Quality score 92.",
         "sender": "Brian Holloway", "quality_score": 92, "type": "call"},
        {"id": "act-002", "timestamp": f"{t}T08:42:00-07:00", "action_type": "lead_created",
         "description": "Created lead — Sandra Kowalski, Cascade Logistics wire decking quote request.",
         "sender": "Sandra Kowalski", "quality_score": 87, "type": "email"},
        {"id": "act-003", "timestamp": f"{t}T08:04:00-07:00", "action_type": "not_qualified",
         "description": "Call screened — residential garage shelving inquiry. Not qualified, referred out.",
         "sender": "Unknown Caller", "quality_score": 12, "type": "call"},
        {"id": "act-015", "timestamp": f"{t}T10:23:00-07:00", "action_type": "lead_created",
         "description": "Created lead — Rachel Dunn, Kent cold storage drive-in racking. 6,000 sq ft.",
         "sender": "Rachel Dunn", "quality_score": 91, "type": "call"},
        {"id": "act-016", "timestamp": f"{t}T10:06:00-07:00", "action_type": "invoice_logged",
         "description": "Supplier email logged — Northwest Steel Supply PO-2026-048 shipped, ETA Wednesday.",
         "sender": "Northwest Steel Supply", "quality_score": 80, "type": "email"},
        {"id": "act-017", "timestamp": f"{t}T09:49:00-07:00", "action_type": "lead_created",
         "description": "Created lead — Luis Medina, carton flow rack replacement. Photos received.",
         "sender": "Luis Medina", "quality_score": 76, "type": "sms"},
        {"id": "act-018", "timestamp": f"{t}T11:16:00-07:00", "action_type": "lead_created",
         "description": "Created lead — Puget Sound Brewing, keg racking for taproom warehouse.",
         "sender": "Puget Sound Brewing", "quality_score": 84, "type": "call"},
        {"id": "act-019", "timestamp": f"{t}T11:03:00-07:00", "action_type": "lead_created",
         "description": "Created lead — Valerie Chang, Premier Paper quote 2026-Q-022 approved with revision.",
         "sender": "Valerie Chang", "quality_score": 94, "type": "email"},
        {"id": "act-020", "timestamp": f"{t}T07:46:00-07:00", "action_type": "spam_blocked",
         "description": "Spam call blocked — automated warranty extension robo-call.",
         "sender": "Robo-call", "quality_score": 1, "type": "call"},
        {"id": "act-021", "timestamp": f"{t}T13:11:00-07:00", "action_type": "lead_created",
         "description": "Created lead — David Park, Everett auto parts distributor. 8,000 sq ft pallet racking.",
         "sender": "David Park", "quality_score": 88, "type": "call"},
        {"id": "act-022", "timestamp": f"{t}T13:46:00-07:00", "action_type": "lead_created",
         "description": "Created lead — Cascade Logistics, add-on quote for 20 wire deck panels.",
         "sender": "Cascade Logistics", "quality_score": 82, "type": "email"},
        {"id": "act-023", "timestamp": f"{t}T14:21:00-07:00", "action_type": "forwarded",
         "description": "Call from Maria Santana forwarded to Jay — food bank shelving, non-profit discount inquiry.",
         "sender": "Maria Santana", "quality_score": 58, "type": "call"},
        {"id": "act-024", "timestamp": f"{t}T07:31:00-07:00", "action_type": "invoice_logged",
         "description": "Supplier email logged — Unarco Industries payment reminder INV-U-2026-088, $6,240 due.",
         "sender": "Unarco Industries", "quality_score": 72, "type": "email"},
        # ── Yesterday (12 items) ──
        {"id": "act-004", "timestamp": f"{y}T16:23:00-07:00", "action_type": "forwarded",
         "description": "SMS from Derek Tran forwarded to Jay — quote status follow-up for Tran Distribution.",
         "sender": "Derek Tran", "quality_score": 55, "type": "sms"},
        {"id": "act-005", "timestamp": f"{y}T14:56:00-07:00", "action_type": "lead_created",
         "description": "Created lead — Marcus Webb, Auburn cantilever racking. $18K budget. Quality score 95.",
         "sender": "Marcus Webb", "quality_score": 95, "type": "call"},
        {"id": "act-006", "timestamp": f"{y}T11:31:00-07:00", "action_type": "invoice_logged",
         "description": "Supplier email logged — PFP Freight PO-2026-041 delivery confirmation, ETA March 19.",
         "sender": "PFP Freight Systems", "quality_score": 78, "type": "email"},
        {"id": "act-007", "timestamp": f"{y}T15:19:00-07:00", "action_type": "lead_created",
         "description": "Created lead — Gina Reyes, quote 2026-Q-019 approved. Install scheduled April 7.",
         "sender": "Gina Reyes", "quality_score": 98, "type": "call"},
        {"id": "act-008", "timestamp": f"{y}T10:45:00-07:00", "action_type": "lead_created",
         "description": "Created lead — Tony Marchetti, mezzanine platform inquiry. Site visit offered.",
         "sender": "Tony Marchetti", "quality_score": 71, "type": "sms"},
        {"id": "act-009", "timestamp": f"{y}T09:05:00-07:00", "action_type": "spam_blocked",
         "description": "Spam call blocked — auto insurance robo-call. No action taken.",
         "sender": "Auto Insurance Spam", "quality_score": 2, "type": "call"},
        {"id": "act-010", "timestamp": f"{y}T13:56:00-07:00", "action_type": "forwarded",
         "description": "Email from Kim Wholesale flagged for Jay — invoice dispute on INV-2026-010.",
         "sender": "Kim Wholesale Group", "quality_score": 60, "type": "email"},
        {"id": "act-025", "timestamp": f"{y}T09:31:00-07:00", "action_type": "lead_created",
         "description": "Created lead — Steve Nakamura, Renton e-commerce fulfillment pick module shelving.",
         "sender": "Steve Nakamura", "quality_score": 90, "type": "call"},
        {"id": "act-026", "timestamp": f"{y}T08:16:00-07:00", "action_type": "invoice_logged",
         "description": "Supplier email logged — Ridgeline Fasteners INV-RF-1187 anchor bolts, $1,890 net 30.",
         "sender": "Ridgeline Fasteners", "quality_score": 75, "type": "email"},
        {"id": "act-027", "timestamp": f"{y}T11:46:00-07:00", "action_type": "lead_created",
         "description": "Created lead — Priya Sharma, pharmacy distribution narrow-aisle racking. Seismic compliance.",
         "sender": "Priya Sharma", "quality_score": 86, "type": "call"},
        {"id": "act-028", "timestamp": f"{y}T15:41:00-07:00", "action_type": "lead_created",
         "description": "Created lead — Emerald City Distributors, beverage warehouse pushback racking. $35K budget.",
         "sender": "Emerald City Distributors", "quality_score": 93, "type": "call"},
        {"id": "act-029", "timestamp": f"{y}T08:03:00-07:00", "action_type": "not_qualified",
         "description": "Call screened — wrong number, looking for dentist office. 12 seconds.",
         "sender": "Unknown Caller", "quality_score": 3, "type": "call"},
    ]


def _build_weekly_demo():
    activity = _build_activity_demo()
    return {
        "this_week": {
            "leads": sum(1 for a in activity if a["action_type"] == "lead_created"),
            "invoices": sum(1 for a in activity if a["action_type"] == "invoice_logged"),
            "calls": sum(1 for a in activity if a["type"] == "call"),
            "not_qualified": sum(1 for a in activity if a["action_type"] in ("not_qualified", "spam_blocked")),
            "messages": len(activity)
        },
        "last_week": {"leads": 4, "invoices": 3, "calls": 11, "not_qualified": 4, "messages": 18}
    }


@ash_bp.route("/api/ash/inbox", methods=["GET"])
@require_auth
def api_ash_inbox():
    """
    Returns all processed Ash inbox items sorted newest first.
    Pulls live calls from Retell API via get_recent_calls().
    Optional filter: ?type=call|email|sms
    Fields: id, type, sender, sender_contact, summary, outcome,
            quality_score, timestamp, duration_seconds, lead_id
    """
    try:
        from utils.retell_client import get_recent_calls
        calls = get_recent_calls()

        sentiment_map = {
            "Positive": 90,
            "Neutral": 70,
            "Negative": 40,
            "Unknown": 60
        }

        items = []
        for call in (calls or []):
            phone = call.get("phone_number", "")
            sentiment = call.get("user_sentiment", "Unknown")
            outcome = "not_qualified" if sentiment == "Negative" else "lead_created"

            items.append({
                "id": call.get("call_id", ""),
                "type": "call",
                "sender": call.get("caller_name") or phone or "Unknown Caller",
                "sender_contact": phone,
                "summary": call.get("call_summary") or "Inbound call",
                "outcome": outcome,
                "quality_score": sentiment_map.get(sentiment, 60),
                "timestamp": _format_retell_timestamp(call.get("start_timestamp")),
                "duration_seconds": None,
                "lead_id": None,
            })

        # Merge in stored SMS messages
        for sms in get_sms_messages():
            items.append({
                "id": sms["id"],
                "type": "sms",
                "sender": sms["from_number"],
                "sender_contact": sms["from_number"],
                "summary": sms["body"],
                "outcome": "forwarded",
                "quality_score": 60,
                "timestamp": sms["created_at"],
                "duration_seconds": None,
                "lead_id": None,
            })

        if not items:
            items = _build_inbox_demo()

        # Sort all items newest first
        items.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

        item_type = request.args.get("type")
        if item_type and item_type in ("call", "email", "sms"):
            items = [i for i in items if i["type"] == item_type]

        return jsonify({"items": items, "count": len(items)})

    except Exception as e:
        items = _build_inbox_demo()
        # Still include SMS on fallback
        for sms in get_sms_messages():
            items.append({
                "id": sms["id"],
                "type": "sms",
                "sender": sms["from_number"],
                "sender_contact": sms["from_number"],
                "summary": sms["body"],
                "outcome": "forwarded",
                "quality_score": 60,
                "timestamp": sms["created_at"],
                "duration_seconds": None,
                "lead_id": None,
            })
        items.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        item_type = request.args.get("type")
        if item_type and item_type in ("call", "email", "sms"):
            items = [i for i in items if i["type"] == item_type]
        return jsonify({"items": items, "count": len(items), "error": str(e)})


@ash_bp.route("/api/ash/inbox/stats", methods=["GET"])
@require_auth
def api_ash_inbox_stats():
    """
    Returns today's Ash inbox counts from live Retell API.
    Fields: total, leads_created, invoices, not_qualified
    """
    try:
        from utils.retell_client import get_recent_calls
        calls = get_recent_calls()

        today = _today_str()
        today_items = []
        for call in (calls or []):
            ts = _format_retell_timestamp(call.get("start_timestamp"))
            if ts and ts.startswith(today):
                sentiment = call.get("user_sentiment", "Unknown")
                outcome = "not_qualified" if sentiment == "Negative" else "lead_created"
                today_items.append({"outcome": outcome})

        total = len(today_items)
        leads_created = sum(1 for i in today_items if i["outcome"] == "lead_created")
        invoices = sum(1 for i in today_items if i["outcome"] == "invoice_logged")
        not_qualified = sum(1 for i in today_items if i["outcome"] == "not_qualified")

        return jsonify({
            "total": total,
            "leads_created": leads_created,
            "invoices": invoices,
            "not_qualified": not_qualified
        })

    except Exception as e:
        today = _today_str()
        today_items = [i for i in _build_inbox_demo()
                       if i["timestamp"].startswith(today)]
        return jsonify({
            "total": len(today_items),
            "leads_created": sum(1 for i in today_items if i["outcome"] == "lead_created"),
            "invoices": sum(1 for i in today_items if i["outcome"] == "invoice_logged"),
            "not_qualified": sum(1 for i in today_items if i["outcome"] == "not_qualified"),
            "error": str(e)
        })


@ash_bp.route("/api/ash/bookkeeping", methods=["GET"])
@require_auth
def api_ash_bookkeeping():
    """
    Returns bookkeeping & accounting demo items.
    Fields: id, category, vendor, description, amount, status, due_date, timestamp
    """
    items = _build_bookkeeping_demo()
    return jsonify({"items": items, "count": len(items)})


@ash_bp.route("/api/ash/activity", methods=["GET"])
@require_auth
def api_ash_activity():
    try:
        from utils.retell_client import get_recent_calls
        calls = get_recent_calls()

        sentiment_map = {
            "Positive": 90,
            "Neutral": 70,
            "Negative": 40,
            "Unknown": 60
        }

        items = []
        for call in (calls or []):
            phone = call.get("phone_number", "")
            action_type = "outbound_call" if call.get("direction") == "outbound" else "inbound_call"
            sentiment = call.get("user_sentiment", "Unknown")
            items.append({
                "id": call.get("call_id", ""),
                "timestamp": _format_retell_timestamp(call.get("start_timestamp")),
                "action_type": action_type,
                "description": call.get("call_summary") or "No summary available",
                "sender": call.get("caller_name") or phone or "Unknown Caller",
                "quality_score": sentiment_map.get(sentiment, 60),
                "type": "call"
            })

        # Fall back to demo data if no real calls
        if not items:
            items = _build_activity_demo()

        return jsonify({
            "activity": items,
            "count": len(items)
        })
    except Exception as e:
        return jsonify({
            "activity": _build_activity_demo(),
            "count": 0,
            "error": str(e)
        })


@ash_bp.route("/api/ash/weekly", methods=["GET"])
@require_auth
def api_ash_weekly():
    """
    Returns this week vs last week comparison counts.
    Fields: this_week, last_week — each with leads, invoices,
            calls, not_qualified, messages
    """
    return jsonify(_build_weekly_demo())


@ash_bp.route("/api/ash/overview")
@require_auth
def ash_overview():
    return jsonify({
        "calls_today": 14,
        "calls_answered": 11,
        "calls_missed": 3,
        "avg_call_duration": "3m 42s",
        "top_caller": "Ace Logistics",
        "sentiment": "positive",
        "open_quotes": 7,
        "quotes_pending_followup": 3,
        "insight_summary": "Call volume is up 18% vs last week. Three missed calls from Ace Logistics — recommend follow-up today.",
        "weekly_calls": [8, 12, 10, 14, 9, 6, 14]
    })


# ── Retell API Routes ─────────────────────────────────────────────────────────

@ash_bp.route("/api/ash/calls", methods=["GET"])
@require_auth
def api_ash_calls():
    """Return recent Retell calls via direct API pull."""
    calls = get_recent_calls(10)
    return jsonify(calls)


@ash_bp.route("/api/ash/calls/<call_id>", methods=["GET"])
@require_auth
def api_ash_call_detail(call_id):
    """Return full detail for a single Retell call."""
    detail = get_call_detail(call_id)
    if detail is None:
        return jsonify({"error": "Call not found or API error"}), 404
    return jsonify(detail)

