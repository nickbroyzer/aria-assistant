"""
Ash scanner blueprint — Gmail inbox scanning for supplier-related emails.

Routes:
  /api/ash/scan                   → GET scan inbox for supplier emails
  /api/ash/status                 → GET Gmail connection status
  /oauth/gmail/start              → GET redirect to Gmail OAuth flow
  /oauth/gmail/callback           → GET handle OAuth callback
"""

from flask import Blueprint, jsonify, redirect, request, session, url_for

from utils.auth import require_auth
from utils.gmail_auth import (
    is_gmail_connected, gmail_auth_url, gmail_exchange_code,
    get_gmail_account_info,
)
from utils.ash_scanner import scan_inbox


ash_bp = Blueprint("ash", __name__)


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

ASH_INBOX_DEMO = [
    {
        "id": "item-001",
        "type": "call",
        "sender": "Brian Holloway",
        "sender_contact": "+1 (253) 847-2291",
        "summary": "Inquired about pallet racking installation for a 12,000 sq ft warehouse in Tacoma. Has existing concrete anchoring. Wants quote by end of week.",
        "outcome": "lead_created",
        "quality_score": 92,
        "timestamp": "2026-03-15T09:14:00-07:00",
        "duration_seconds": 187,
        "lead_id": "lead-088"
    },
    {
        "id": "item-002",
        "type": "email",
        "sender": "Sandra Kowalski",
        "sender_contact": "skowalski@cascadelogistics.com",
        "summary": "Requested quote for wire decking on 80 existing pallet rack bays. Attached floor plan. Needs install within 30 days.",
        "outcome": "lead_created",
        "quality_score": 87,
        "timestamp": "2026-03-15T08:41:00-07:00",
        "duration_seconds": None,
        "lead_id": "lead-087"
    },
    {
        "id": "item-003",
        "type": "call",
        "sender": "Unknown Caller",
        "sender_contact": "+1 (206) 555-0193",
        "summary": "Asked about residential garage shelving. Explained Pacific Construction is commercial only. Referred to Home Depot.",
        "outcome": "not_qualified",
        "quality_score": 12,
        "timestamp": "2026-03-15T08:03:00-07:00",
        "duration_seconds": 94,
        "lead_id": None
    },
    {
        "id": "item-004",
        "type": "sms",
        "sender": "Derek Tran",
        "sender_contact": "+1 (425) 918-4477",
        "summary": "Texted asking for status update on quote for Tran Distribution. Forwarded to Jay for follow-up.",
        "outcome": "forwarded",
        "quality_score": 55,
        "timestamp": "2026-03-14T16:22:00-07:00",
        "duration_seconds": None,
        "lead_id": None
    },
    {
        "id": "item-005",
        "type": "call",
        "sender": "Marcus Webb",
        "sender_contact": "+1 (360) 204-8832",
        "summary": "Needs cantilever racking for lumber storage at Auburn facility. 3,500 sq ft area. Budget around $18,000. Ready to move forward.",
        "outcome": "lead_created",
        "quality_score": 95,
        "timestamp": "2026-03-14T14:55:00-07:00",
        "duration_seconds": 312,
        "lead_id": "lead-086"
    },
    {
        "id": "item-006",
        "type": "email",
        "sender": "PFP Freight Systems",
        "sender_contact": "orders@pfpfreight.com",
        "summary": "Supplier order confirmation for upright frames PO-2026-041. Estimated delivery March 19.",
        "outcome": "invoice_logged",
        "quality_score": 78,
        "timestamp": "2026-03-14T11:30:00-07:00",
        "duration_seconds": None,
        "lead_id": None
    },
    {
        "id": "item-007",
        "type": "call",
        "sender": "Gina Reyes",
        "sender_contact": "+1 (253) 771-0045",
        "summary": "Follow-up on quote 2026-Q-019 for Reyes Cold Storage. Approved the quote, wants to schedule install for April 7.",
        "outcome": "lead_created",
        "quality_score": 98,
        "timestamp": "2026-03-13T15:18:00-07:00",
        "duration_seconds": 228,
        "lead_id": "lead-085"
    },
    {
        "id": "item-008",
        "type": "sms",
        "sender": "Tony Marchetti",
        "sender_contact": "+1 (206) 444-9921",
        "summary": "Asked if Pacific Construction handles mezzanine platforms. Ash confirmed yes and offered to schedule a site visit.",
        "outcome": "lead_created",
        "quality_score": 71,
        "timestamp": "2026-03-13T10:44:00-07:00",
        "duration_seconds": None,
        "lead_id": "lead-084"
    },
    {
        "id": "item-009",
        "type": "call",
        "sender": "Auto Insurance Spam",
        "sender_contact": "+1 (888) 201-5544",
        "summary": "Automated spam call. No action taken.",
        "outcome": "not_qualified",
        "quality_score": 2,
        "timestamp": "2026-03-13T09:05:00-07:00",
        "duration_seconds": 11,
        "lead_id": None
    },
    {
        "id": "item-010",
        "type": "email",
        "sender": "Kim Wholesale Group",
        "sender_contact": "rkim@kimwholesale.com",
        "summary": "Invoice dispute on INV-2026-010. Claims wire decking quantity billed is incorrect. Flagged for Jay review.",
        "outcome": "forwarded",
        "quality_score": 60,
        "timestamp": "2026-03-12T13:55:00-07:00",
        "duration_seconds": None,
        "lead_id": None
    }
]

ASH_ACTIVITY_DEMO = [
    {
        "id": "act-001",
        "timestamp": "2026-03-15T09:15:00-07:00",
        "action_type": "lead_created",
        "description": "Created lead — Brian Holloway, Tacoma warehouse racking inquiry. Quality score 92.",
        "sender": "Brian Holloway",
        "quality_score": 92,
        "type": "call"
    },
    {
        "id": "act-002",
        "timestamp": "2026-03-15T08:42:00-07:00",
        "action_type": "lead_created",
        "description": "Created lead — Sandra Kowalski, Cascade Logistics wire decking quote request.",
        "sender": "Sandra Kowalski",
        "quality_score": 87,
        "type": "email"
    },
    {
        "id": "act-003",
        "timestamp": "2026-03-15T08:04:00-07:00",
        "action_type": "not_qualified",
        "description": "Call screened — residential garage shelving inquiry. Not qualified, referred out.",
        "sender": "Unknown Caller",
        "quality_score": 12,
        "type": "call"
    },
    {
        "id": "act-004",
        "timestamp": "2026-03-14T16:23:00-07:00",
        "action_type": "forwarded",
        "description": "SMS from Derek Tran forwarded to Jay — quote status follow-up for Tran Distribution.",
        "sender": "Derek Tran",
        "quality_score": 55,
        "type": "sms"
    },
    {
        "id": "act-005",
        "timestamp": "2026-03-14T14:56:00-07:00",
        "action_type": "lead_created",
        "description": "Created lead — Marcus Webb, Auburn cantilever racking. $18K budget. Quality score 95.",
        "sender": "Marcus Webb",
        "quality_score": 95,
        "type": "call"
    },
    {
        "id": "act-006",
        "timestamp": "2026-03-14T11:31:00-07:00",
        "action_type": "invoice_logged",
        "description": "Supplier email logged — PFP Freight PO-2026-041 delivery confirmation, ETA March 19.",
        "sender": "PFP Freight Systems",
        "quality_score": 78,
        "type": "email"
    },
    {
        "id": "act-007",
        "timestamp": "2026-03-13T15:19:00-07:00",
        "action_type": "lead_created",
        "description": "Created lead — Gina Reyes, quote 2026-Q-019 approved. Install scheduled April 7.",
        "sender": "Gina Reyes",
        "quality_score": 98,
        "type": "call"
    },
    {
        "id": "act-008",
        "timestamp": "2026-03-13T10:45:00-07:00",
        "action_type": "lead_created",
        "description": "Created lead — Tony Marchetti, mezzanine platform inquiry. Site visit offered.",
        "sender": "Tony Marchetti",
        "quality_score": 71,
        "type": "sms"
    },
    {
        "id": "act-009",
        "timestamp": "2026-03-13T09:05:00-07:00",
        "action_type": "spam_blocked",
        "description": "Spam call blocked — auto insurance robo-call. No action taken.",
        "sender": "Auto Insurance Spam",
        "quality_score": 2,
        "type": "call"
    },
    {
        "id": "act-010",
        "timestamp": "2026-03-12T13:56:00-07:00",
        "action_type": "forwarded",
        "description": "Email from Kim Wholesale flagged for Jay — invoice dispute on INV-2026-010.",
        "sender": "Kim Wholesale Group",
        "quality_score": 60,
        "type": "email"
    },
    {
        "id": "act-011",
        "timestamp": "2026-03-12T10:20:00-07:00",
        "action_type": "lead_created",
        "description": "Created lead — Pacific Northwest Cold Storage, freezer rack expansion. $42K estimate.",
        "sender": "Pacific Northwest Cold Storage",
        "quality_score": 88,
        "type": "call"
    },
    {
        "id": "act-012",
        "timestamp": "2026-03-11T14:10:00-07:00",
        "action_type": "lead_created",
        "description": "Created lead — Apex 3PL, bulk shelving for new Kent facility. Site visit booked March 18.",
        "sender": "Apex 3PL",
        "quality_score": 82,
        "type": "call"
    },
    {
        "id": "act-013",
        "timestamp": "2026-03-10T11:30:00-07:00",
        "action_type": "not_qualified",
        "description": "Call screened — looking for moving company. Misdial, not qualified.",
        "sender": "Unknown Caller",
        "quality_score": 5,
        "type": "call"
    },
    {
        "id": "act-014",
        "timestamp": "2026-03-10T09:15:00-07:00",
        "action_type": "invoice_logged",
        "description": "Supplier invoice logged — Unarco Industries INV-U-2026-088, $6,240.00 due March 25.",
        "sender": "Unarco Industries",
        "quality_score": 70,
        "type": "email"
    }
]

ASH_WEEKLY_DEMO = {
    "this_week": {
        "leads": 6,
        "invoices": 2,
        "calls": 8,
        "not_qualified": 2,
        "messages": 14
    },
    "last_week": {
        "leads": 4,
        "invoices": 3,
        "calls": 11,
        "not_qualified": 4,
        "messages": 18
    }
}


@ash_bp.route("/api/ash/inbox", methods=["GET"])
@require_auth
def api_ash_inbox():
    """
    Returns all processed Ash inbox items sorted newest first.
    Optional filter: ?type=call|email|sms
    Fields: id, type, sender, sender_contact, summary, outcome,
            quality_score, timestamp, duration_seconds, lead_id
    """
    item_type = request.args.get("type")
    items = ASH_INBOX_DEMO

    if item_type and item_type in ("call", "email", "sms"):
        items = [i for i in items if i["type"] == item_type]

    return jsonify({"items": items, "count": len(items)})


@ash_bp.route("/api/ash/inbox/stats", methods=["GET"])
@require_auth
def api_ash_inbox_stats():
    """
    Returns today's Ash inbox counts.
    Fields: total, leads_created, invoices, not_qualified
    """
    today_items = [i for i in ASH_INBOX_DEMO
                   if i["timestamp"].startswith("2026-03-15")]

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


@ash_bp.route("/api/ash/activity", methods=["GET"])
@require_auth
def api_ash_activity():
    """
    Returns chronological feed of all Ash actions, newest first.
    Fields: id, timestamp, action_type, description
    """
    return jsonify({
        "activity": ASH_ACTIVITY_DEMO,
        "count": len(ASH_ACTIVITY_DEMO)
    })


@ash_bp.route("/api/ash/weekly", methods=["GET"])
@require_auth
def api_ash_weekly():
    """
    Returns this week vs last week comparison counts.
    Fields: this_week, last_week — each with leads, invoices,
            calls, not_qualified, messages
    """
    return jsonify(ASH_WEEKLY_DEMO)

