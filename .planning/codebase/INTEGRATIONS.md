# External Integrations

**Analysis Date:** 2025-02-19

## APIs & External Services

**Anthropic Claude:**
- Claude API for conversational chat and lead extraction
- SDK: `anthropic` 0.84.0
- Model: `claude-sonnet-4-6` (primary model in `routes/chat.py`)
- Auth: `ANTHROPIC_API_KEY` environment variable (stored in `.env` and `config.json`)
- Scope: Chat widget, lead scoring, email drafting, lead/appointment suggestions
- Usage: Streaming responses via SSE in `/chat` endpoint

**Google Calendar:**
- Calendar availability lookup and event booking
- SDK: `google-api-python-client` 2.192.0
- Auth: OAuth 2.0 flow with stored credentials
  - Credentials: `google_credentials.json` (client config)
  - Token: `google_token.json` (cached authorization)
  - Scope: `https://www.googleapis.com/auth/calendar`
- Config: `CALENDAR_ID` and `CALENDAR_EMAIL` in `config.json` integrations section
- Endpoint: `get_calendar_service()` in `utils/calendar.py` lines 24-33
- Usage: Appointment availability (`get_available_slots()`), event creation via `/book-appointment`

**Gmail:**
- Email sending (lead notifications, follow-up outreach, invoice alerts)
- IMAP polling for vendor invoice inbox
- SDK: `google-api-python-client` 2.192.0 (read) + smtplib stdlib (send)
- Auth: OAuth 2.0 OR Gmail App Password
  - OAuth: `gmail_credentials.json` + `gmail_token.json`
  - Scope: `https://www.googleapis.com/auth/gmail.readonly`
  - App Password: `GMAIL_APP_PASSWORD` (legacy fallback for SMTP)
- Credentials:
  - Sender: `GMAIL_SENDER` env var (e.g., `leads.pacificconstruction@gmail.com`)
  - Invoice inbox: `INVOICE_INBOX_EMAIL` + `INVOICE_INBOX_PASSWORD` in integrations
- SMTP: `smtp.gmail.com:465` (SSL in `utils/email.py` lines 101, 163, 235)
- IMAP: `imap.gmail.com` (polling in `utils/invoice_inbox.py` line 123)
- Usage:
  - Lead notifications: `send_lead_email()` in `utils/email.py` lines 77-105
  - Follow-up outreach: `send_followup_email()` in `utils/email.py` lines 110-168
  - Invoice alerts: `send_invoice_notification()` in `utils/email.py` lines 206-239
  - Invoice polling: `poll_invoice_inbox()` in `utils/invoice_inbox.py` lines 107-233

**Google Sheets (Webhook):**
- Optional webhook for exporting data to Sheets
- Env var: `SHEETS_WEBHOOK` (not required)
- Usage: Referenced in `utils/data.py` line 16 for potential data sync

**DuckDuckGo Web Search:**
- Web search for industry questions (fallback/supplement to Claude)
- SDK: `duckduckgo_search` 8.1.1
- No auth required
- Usage: `web_search()` in `utils/search.py`

## Data Storage

**Databases:**
- SQLite 3
  - File: `utils/data/suppliers.db`
  - Connection: `utils/suppliers_db.py` lines 21-34
  - Client: Native sqlite3 stdlib
  - WAL mode enabled (line 25), foreign keys enforced (line 26)
  - Tables: suppliers, supplier_transactions, supplier_notes
  - Init: `init_db()` + `seed_if_empty()` called on app startup in `app.py` lines 26-28

**File Storage:**
- Local filesystem only (project root JSON files)
- Jobs: `jobs.json`
- Invoices: `invoices.json` (client invoices)
- Job Costs: `jobcosts.json` (labor + materials tracking)
- Vendor Invoices: `vendorinvoices.json`
- Leads: `leads.jsonl` (append-only, one record per line)
- Lead Metadata: `lead_meta.json` (statuses: new/contacted/qualified/converted/lost)
- Lead Communications: `lead_comms.json` (email, call history)
- Job Communications: `job_comms.json` (notes, emails)
- Users: `users.json` (credentials, roles, permissions)
- Payroll: `payroll.json` (pay records, rates)
- Activity Log: `activity_log.jsonl` (append-only audit trail)
- Lead Nurtures: `lead_nurtures.json` (active email sequences)
- Quote Follow-ups: `followups.json` (auto-email campaigns)
- Invoice Inbox: `invoice_inbox.json` (review queue with extracted PDFs)
- Configuration: `config.json` (company, notifications, dashboard, integrations settings)
- File locking: `utils/file_locks.py` prevents corruption during concurrent writes

**Caching:**
- None detected (client-side session state only)

## Authentication & Identity

**Auth Provider:**
- Custom Flask sessions + password hashing
- Implementation in `utils/auth.py`:
  - `@require_auth` decorator for protected routes (line 17)
  - `load_users()` / `save_users()` for user management
  - Password hashes using werkzeug: `generate_password_hash()`, `check_password_hash()`

**User Types:**
- Owner (jay) - Full permissions
- Staff (ashley) - Limited permissions
- Accountant/Bookkeeper (bookkeeper) - Finance-only access
- Stored in `users.json` with roles and permission toggles

**Master Password:**
- Fallback authentication if no user account exists
- `MASTER_PASSWORD` env var (same as `DASHBOARD_PASSWORD`)
- Sets session user_id to "owner-jay" in `routes/dashboard.py` line 98

**Developer Access:**
- `DEV_PASSWORD` env var unlocks Integrations tab in Settings
- Check: `_check_dev_password()` in `utils/config.py`

**OAuth Integrations:**
- Google Calendar: OAuth 2.0 redirect flow (`authorize_calendar.py`)
- Gmail: Direct OAuth 2.0 token exchange in `utils/gmail_auth.py` lines 65-115
- Scopes: calendar (read/write), gmail (read-only)

## Monitoring & Observability

**Error Tracking:**
- None detected (no Sentry, Rollbar, or similar)
- Errors logged to stdout/stderr

**Logs:**
- Console output during development
- Activity audit trail via `activity_log.jsonl` (append-only)
- Logged via `log_activity()` in `utils/activity.py`
- Records: action, description, actor (current user), timestamp, metadata

**Debugging:**
- Flask debug=False (production-safe) in `app.py`
- Template auto-reload enabled for development

## CI/CD & Deployment

**Hosting:**
- Flask dev server (development)
- Gunicorn WSGI (production recommended)
- Environment: Any system with Python 3.14+

**CI Pipeline:**
- None detected (no GitHub Actions, GitLab CI, or similar)

## Environment Configuration

**Required env vars:**
- `ANTHROPIC_API_KEY` - Claude API key (required for chat)
- `SECRET_KEY` - Flask session secret (required to start)
- `GMAIL_SENDER` - Gmail address for email sending
- `GMAIL_APP_PASSWORD` - Gmail app password for SMTP (alternative to OAuth)
- `LEAD_NOTIFY_EMAIL` - Email address to notify on new leads
- `MASTER_PASSWORD` (optional) - Dashboard fallback password
- `DEV_PASSWORD` (optional) - Integrations tab access code

**Optional env vars:**
- `PORT` - Server port (default 5000, set to 5001 in memory)
- `TEMPLATES_AUTO_RELOAD` - Set to "1" for development
- `SHEETS_WEBHOOK` - Google Sheets export endpoint
- `DASHBOARD_PASSWORD` - Alias for `MASTER_PASSWORD`
- `TESTING` - Disable background threads for tests
- `SUPPLIERS_DB` - Custom SQLite DB path (defaults to `utils/data/suppliers.db`)
- `INVOICE_INBOX_EMAIL` - Dedicated Gmail for invoice polling (overrides `GMAIL_SENDER`)
- `INVOICE_INBOX_PASSWORD` - Password for invoice inbox (overrides `GMAIL_APP_PASSWORD`)

**Config file (.env):**
- `.env` in project root (not committed, never read by mapping tools)
- Loaded via `python-dotenv` in `app.py` line 10 and `utils/constants.py` line 10

## Webhooks & Callbacks

**Incoming:**
- Google OAuth callback: `http://localhost:5000/oauth/gmail/callback` (redirect URI in `utils/gmail_auth.py` line 26)
- No public webhooks for external services

**Outgoing:**
- Google Sheets webhook: `SHEETS_WEBHOOK` env var (optional, unused in current codebase)
- No active outgoing webhooks detected

## Integration Connection Details

**Gmail OAuth Setup:**
1. Create credentials at `console.cloud.google.com` → Project "pacific-construction-assistant"
2. Client ID/secret stored in `gmail_credentials.json`
3. Authorization flow: User → `accounts.google.com` → redirect to `/oauth/gmail/callback`
4. Token stored in `gmail_token.json` for reuse
5. Auto-refresh when expired via `get_gmail_service()` in `utils/gmail_auth.py` lines 135-141

**Calendar OAuth Setup:**
1. Create OAuth credentials for "google_credentials.json" (installed app type)
2. Flow initiated via `authorize_calendar.py` (manual, not automated)
3. Token stored in `google_token.json`
4. Service object built via `get_calendar_service()` in `utils/calendar.py` lines 24-33

**Invoice Inbox (IMAP):**
1. Requires dedicated Gmail account (e.g., `pacificconstruction.invoices@gmail.com`)
2. Setup: Enable IMAP, generate Google App Password
3. Connection: `imaplib.IMAP4_SSL("imap.gmail.com")` in `utils/invoice_inbox.py` line 123
4. Polling: Every 30 minutes via daemon thread (`_start_invoice_poller()` in `utils/invoice_inbox.py` lines 236-246)
5. PDF extraction: `pdfplumber` library (line 14)
6. Auto-categorization and job matching (lines 79-104)
7. Review queue: `invoice_inbox.json` with status "pending_review"

**Config Integration Values:**
- Stored in `config.json` → `integrations` object
- Read via `_integ_val(key)` helper in `utils/config.py`
- Examples:
  - `CALENDAR_ID` - Google Calendar ID (default "primary")
  - `CALENDAR_EMAIL` - Calendar account email
  - `GMAIL_SENDER` - Email sender address
  - `GMAIL_APP_PASSWORD` - Password for SMTP

---

*Integration audit: 2025-02-19*
