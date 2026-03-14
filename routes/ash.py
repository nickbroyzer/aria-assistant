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
