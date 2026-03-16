# Technology Stack

**Analysis Date:** 2025-02-19

## Languages

**Primary:**
- Python 3.14.3 - Server-side application backend, data processing, email/calendar integrations

**Secondary:**
- JavaScript (vanilla) - Frontend interactivity in `templates/dashboard.html` and `templates/index.html`
- HTML/CSS - Page templates and styling

## Runtime

**Environment:**
- CPython 3.14.3 (Python)

**Package Manager:**
- pip
- Lockfile: `requirements.txt` (present)

## Frameworks

**Core:**
- Flask 3.1.3 - Web framework, request routing, templating engine
- Jinja2 3.1.6 - Template engine for server-side HTML rendering

**API & Data Processing:**
- anthropic 0.84.0 - Claude API integration for chat, web search, lead extraction
- google-api-python-client 2.192.0 - Google Calendar and Gmail API client
- google-auth 2.49.0 - OAuth 2.0 authentication for Google services
- google-auth-oauthlib 1.3.0 - OAuth 2.0 flow implementation for Google
- requests 2.32.5 - HTTP client for API calls and webhooks

**PDF & Document Processing:**
- pdfplumber 0.11.9 - PDF text extraction for invoice inbox
- PyMuPDF 1.27.1 - PDF manipulation
- pypdfium2 5.6.0 - PDF parsing library
- pdfminer.six 20251230 - PDF content extraction
- lxml 6.0.2 - XML/HTML parsing

**Web Server:**
- gunicorn 25.1.1 - WSGI HTTP server for production deployment
- Werkzeug 3.1.6 - WSGI utility library (included with Flask)

**Utilities:**
- python-dotenv 1.2.2 - Environment variable management from `.env`
- Pillow 12.1.1 - Image processing for logo uploads
- pydantic 2.12.5 - Data validation

## Key Dependencies

**Critical:**
- anthropic 0.84.0 - Powers conversational chat, lead scoring, web search, email drafting
- google-api-python-client 2.192.0 - Google Calendar availability, event booking
- google-auth-oauthlib 1.3.0 - OAuth flow for Gmail and Calendar authorization
- requests 2.32.5 - HTTP requests for webhooks, API calls, IMAP connections

**Infrastructure:**
- pdfplumber 0.11.9 - Automated invoice text extraction for inbox review queue
- Flask 3.1.3 - REST API backend for dashboard, chat widget, admin functions
- smtplib (stdlib) - Gmail SMTP for sending lead notifications, follow-up emails, payment reminders

## Configuration

**Environment:**
- `.env` file (present, not committed) - Stores secrets:
  - `ANTHROPIC_API_KEY` - Claude API key
  - `GMAIL_SENDER` - Gmail address for sending emails
  - `GMAIL_APP_PASSWORD` - Gmail app password (OAuth alternative)
  - `LEAD_NOTIFY_EMAIL` - Lead notification recipient
  - `SECRET_KEY` - Flask session secret
  - `MASTER_PASSWORD` - Dashboard owner password
  - `DEV_PASSWORD` - Integrations tab unlock code
  - `SHEETS_WEBHOOK` - Google Sheets webhook endpoint
  - `TEMPLATES_AUTO_RELOAD` - Flask template caching control

**API Credentials:**
- `google_credentials.json` - Google OAuth 2.0 client credentials (Calendar/Calendar API)
- `gmail_credentials.json` - Gmail OAuth 2.0 client credentials (Gmail read-only access)
- `google_token.json` - Cached Google Calendar OAuth token
- `gmail_token.json` - Cached Gmail OAuth token

**Data Persistence:**
- `config.json` - Application settings (company info, notifications, integrations, dashboard preferences)
- JSON data files - Jobs, invoices, costs, leads, users, payroll (flat-file JSON storage)
- JSONL files - Activity logs, lead records (append-only line-delimited JSON)
- SQLite - `utils/data/suppliers.db` for supplier management with transaction history

## Build & Development

**Run Command (Development):**
```bash
PORT=5001 python app.py
```

**Run Command (Production):**
```bash
gunicorn --bind 0.0.0.0:5001 app:app
```

**Template Auto-Reload:**
- Enabled via `app.config['TEMPLATES_AUTO_RELOAD'] = True` in `app.py` (line 16)
- Required after modifying `templates/dashboard.html`

**Background Threads:**
- Lead/quote follow-up scheduler (`_start_followup_scheduler()` in `utils/sequences.py`)
- Invoice inbox poller (`_start_invoice_poller()` in `utils/invoice_inbox.py`) — polls IMAP every 30 minutes

## Platform Requirements

**Development:**
- macOS or Linux
- Python 3.14+
- Virtual environment: `venv/` directory exists
- Port 5001 (configured in memory; 5000 blocked by macOS AirPlay)

**Production:**
- Python 3.14+ runtime
- SMTP/IMAP access to Gmail (for lead emails, vendor invoice polling)
- Google OAuth applications configured (Calendar, Gmail)
- Environment variables: `ANTHROPIC_API_KEY`, `GMAIL_SENDER`, `GMAIL_APP_PASSWORD`, `SECRET_KEY`
- File storage: JSON files in project root, SQLite DB in `utils/data/`

## Ports & Services

**Flask App:**
- Default: 5000
- Configured: 5001 (to avoid macOS AirPlay conflict)
- Host: 0.0.0.0 (accessible from network)

**External Services:**
- Gmail SMTP: `smtp.gmail.com:465` (SSL)
- Gmail IMAP: `imap.gmail.com` (for invoice inbox polling)
- Google OAuth: `accounts.google.com`, `oauth2.googleapis.com`
- Claude API: Anthropic cloud service
- DuckDuckGo: Web search fallback

---

*Stack analysis: 2025-02-19*
