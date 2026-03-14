"""
Gmail OAuth authentication and token management.

Uses direct requests-based OAuth 2.0 flow (no google_auth_oauthlib.flow,
no PKCE). Handles authorization URL generation, token exchange, refresh,
and credential storage.

Credentials: gmail_credentials.json (project root)
Token file:  gmail_token.json (project root)
Scope:       https://www.googleapis.com/auth/gmail.readonly
"""

import os
import json
import secrets
import time
from urllib.parse import urlencode

import requests
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from utils.constants import GMAIL_TOKEN, GMAIL_CREDS, GMAIL_SCOPES

REDIRECT_URI = "http://localhost:5000/oauth/gmail/callback"


def _load_client_config():
    """Load client_id and client_secret from gmail_credentials.json."""
    if not os.path.exists(GMAIL_CREDS):
        raise FileNotFoundError(
            f"Gmail credentials not found at {GMAIL_CREDS}. "
            "Set up OAuth credentials in Google Cloud Console."
        )
    with open(GMAIL_CREDS) as f:
        data = json.load(f)
    cfg = data.get("web") or data.get("installed") or {}
    return cfg["client_id"], cfg["client_secret"]


def gmail_auth_url():
    """
    Generate the OAuth authorization URL using direct URL construction.

    Returns:
        tuple: (auth_url, state) — full authorization URL and CSRF state token.
    """
    client_id, _ = _load_client_config()
    state = secrets.token_urlsafe(32)

    params = {
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(GMAIL_SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    auth_url = "https://accounts.google.com/o/oauth2/auth?" + urlencode(params)
    return auth_url, state


def gmail_exchange_code(code, state=None):
    """
    Exchange the authorization code for tokens via direct POST.

    No PKCE, no code_verifier — standard OAuth 2.0 authorization code exchange.

    Args:
        code (str): Authorization code from the OAuth callback.
        state (str, optional): State token (for CSRF verification by caller).

    Returns:
        googleapiclient.discovery.Resource: Authorized Gmail API service object.

    Raises:
        FileNotFoundError: If gmail_credentials.json does not exist.
        RuntimeError: If the token exchange fails.
    """
    client_id, client_secret = _load_client_config()

    resp = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": REDIRECT_URI,
            "grant_type": "authorization_code",
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    if resp.status_code != 200:
        raise RuntimeError(f"Token exchange failed ({resp.status_code}): {resp.text}")

    token_data = resp.json()

    # Build a token file compatible with google.oauth2.credentials
    token_info = {
        "token": token_data["access_token"],
        "refresh_token": token_data.get("refresh_token"),
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": client_id,
        "client_secret": client_secret,
        "scopes": GMAIL_SCOPES,
        "expiry": _expiry_from_seconds(token_data.get("expires_in", 3600)),
    }
    with open(GMAIL_TOKEN, "w") as f:
        json.dump(token_info, f, indent=2)

    creds = Credentials.from_authorized_user_file(GMAIL_TOKEN, GMAIL_SCOPES)
    return build("gmail", "v1", credentials=creds)


def get_gmail_service():
    """
    Return an authorized Gmail API service object.

    Loads stored credentials and refreshes if expired.

    Returns:
        googleapiclient.discovery.Resource or None
    """
    creds = None

    if os.path.exists(GMAIL_TOKEN):
        try:
            creds = Credentials.from_authorized_user_file(GMAIL_TOKEN, GMAIL_SCOPES)
        except Exception:
            creds = None

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            with open(GMAIL_TOKEN, "w") as f:
                f.write(creds.to_json())
        except Exception:
            creds = None

    if not creds or not creds.valid:
        return None

    return build("gmail", "v1", credentials=creds)


def is_gmail_connected():
    """
    Check if valid Gmail OAuth tokens exist.

    Returns:
        bool
    """
    if not os.path.exists(GMAIL_TOKEN):
        return False
    try:
        creds = Credentials.from_authorized_user_file(GMAIL_TOKEN, GMAIL_SCOPES)
        if creds.expired and not creds.refresh_token:
            return False
        return True
    except Exception:
        return False


def get_gmail_account_info():
    """
    Get the email address associated with the Gmail OAuth token.

    Returns:
        str or None
    """
    service = get_gmail_service()
    if not service:
        return None
    try:
        profile = service.users().getProfile(userId="me").execute()
        return profile.get("emailAddress")
    except Exception:
        return None


def _expiry_from_seconds(expires_in):
    """Convert expires_in seconds to an ISO 8601 expiry timestamp."""
    from datetime import datetime, timezone, timedelta
    expiry = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    return expiry.isoformat()
