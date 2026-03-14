# Ash Gmail Scanner — Changes Summary

**Project:** Pacific Construction Dashboard
**Date:** March 14, 2026
**Status:** ✅ Working end-to-end

---

## What Was Done

Connected the Pacific Construction dashboard to Gmail via OAuth 2.0 for an AI email scanning feature called "Ash". The scanner reads the `leads.pacificconstruction@gmail.com` inbox, classifies emails (invoice, shipment, delay, order confirmation, tracking), and fuzzy-matches them to suppliers and orders in the database.

---

## Files Created

### 1. `utils/gmail_auth.py` — Gmail OAuth Module (direct requests-based)
- `gmail_auth_url()` — Builds Google OAuth consent URL (no PKCE, no google_auth_oauthlib.flow)
- `gmail_exchange_code(code, state)` — Exchanges auth code for tokens via `requests.post` to `https://oauth2.googleapis.com/token`
- `get_gmail_service()` — Returns authorized Gmail API v1 service (auto-refreshes expired tokens)
- `is_gmail_connected()` — Checks if valid `gmail_token.json` exists
- `get_gmail_account_info()` — Returns connected email address from Gmail profile
- Uses `google.oauth2.credentials.Credentials` for token refresh only

### 2. `utils/ash_scanner.py` — Email Scanner
- `scan_inbox(max_results=50, days_back=7)` — Searches Gmail for supplier keywords, returns structured results
- `classify_email(subject, snippet)` — Regex-based classification into: invoice, shipment, delay, order_confirmation, tracking, general
- `match_supplier(sender, sender_email, suppliers)` — Fuzzy match using SequenceMatcher (60% threshold)
- `match_order(subject, snippet, orders)` — Matches order IDs/PO numbers in email text

### 3. `routes/ash.py` — Flask Blueprint
- `GET /api/ash/scan` — Scan inbox for supplier emails (auth required). Params: `max_results`, `days_back`
- `GET /api/ash/status` — Gmail connection status: `{ connected: bool, email: str }`
- `GET /oauth/gmail/start` — Redirects to Google OAuth consent screen
- `GET /oauth/gmail/callback` — Handles OAuth callback, saves token, redirects to `/dashboard`

### 4. `gmail_credentials.json` — OAuth Web Client Credentials
- Client: "Ash Gmail Scanner" (Web application type)
- Redirect URI: `http://localhost:5000/oauth/gmail/callback`
- Created in Google Cloud project `pacific-construction-assistant`

### 5. `gmail_token.json` — Auto-generated OAuth Token (created after successful auth)
- Contains access_token, refresh_token, scopes
- Auto-refreshes when expired

---

## Files Modified

### 6. `utils/constants.py` — Added Gmail constants
```python
GMAIL_TOKEN  = "gmail_token.json"
GMAIL_CREDS  = "gmail_credentials.json"
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
```

### 7. `routes/__init__.py` — Registered ash blueprint
```python
from routes.ash import ash_bp
# Added ash_bp to ALL_BLUEPRINTS list
```

---

## Google Cloud Setup Completed
1. ✅ Gmail API enabled on project `pacific-construction-assistant`
2. ✅ OAuth consent screen configured with test user `leads.pacificconstruction@gmail.com`
3. ✅ Web OAuth client "Ash Gmail Scanner" created with redirect URI
4. ✅ Client secret generated and saved to `gmail_credentials.json`
5. ✅ OAuth flow tested end-to-end — token saved, dashboard redirect works

---

## Key Fix: PKCE Error Resolution
The original implementation used `google_auth_oauthlib.flow.Flow` which adds PKCE (code_verifier) by default. This caused "Missing code verifier" errors. Rewrote `gmail_auth.py` to use direct `requests`-based OAuth — manually constructing the auth URL and exchanging the code via HTTP POST. No PKCE, no code verifier, clean flow.

---

## API Endpoints

```bash
# Check Gmail connection status
curl http://localhost:5000/api/ash/status
# → { "connected": true, "email": "leads.pacificconstruction@gmail.com" }

# Scan inbox for supplier emails
curl "http://localhost:5000/api/ash/scan?days_back=7&max_results=20"

# Start OAuth flow (browser)
open http://localhost:5000/oauth/gmail/start
```
