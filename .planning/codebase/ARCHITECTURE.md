# Architecture

**Analysis Date:** 2026-03-15

## Pattern Overview

**Overall:** Layered Flask application with blueprint-based routing, persistent JSON/JSONL storage, and background daemon threads for automated workflows.

**Key Characteristics:**
- **Route blueprints** — each feature domain (jobs, leads, invoices, etc.) is a separate Flask blueprint for isolation and reusability
- **Centralized data layer** — all file I/O routed through `utils/data.py` with file-lock synchronization for cross-process safety
- **Config-driven behavior** — settings stored in `config.json`, integration credentials managed via `_integ_val()` helper
- **Background automation** — daemon threads for quote follow-up sequences and Gmail invoice polling start on app boot
- **Activity audit trail** — all significant actions logged to `activity_log.jsonl` with actor attribution

## Layers

**Presentation (Frontend):**
- Purpose: Single-page application UI with dark theme, responsive tables, modals, and real-time data binding
- Location: `templates/dashboard.html` (623KB, all-in-one SPA)
- Contains: HTML/CSS/JavaScript (no build step, vanilla JS with fetch API)
- Depends on: Flask `/dashboard/api/*` endpoints
- Used by: Web browsers (via Flask `render_template`)

**HTTP API (Routes):**
- Purpose: RESTful endpoints for all dashboard operations, organized by domain
- Location: `routes/*.py` (8 blueprints)
- Contains: Flask blueprint definitions with `@require_auth` decorators, request/response handling
- Depends on: Utilities layer (auth, data, email, config, activity)
- Used by: Dashboard JavaScript via fetch, background jobs
- Entry point: `routes/__init__.py` calls `register_blueprints(app)` from `app.py`

**Business Logic & Integrations:**
- Purpose: Sequences, emails, calendar syncing, Gmail inbox polling
- Location: `utils/sequences.py`, `utils/email.py`, `utils/gmail_auth.py`, `utils/calendar.py`, `utils/invoice_inbox.py`
- Contains: Email sending (SMTP), lead/quote nurture state machines, Google Calendar/Gmail OAuth integrations
- Depends on: Data layer, config, constants
- Used by: Routes and background daemons

**Data Access Layer:**
- Purpose: Single source of truth for all persistent storage operations
- Location: `utils/data.py` (9554 bytes)
- Contains: Load/save functions for all entities (jobs, leads, invoices, nurtures, etc.); file-lock wrappers; auto-numbering helpers
- Depends on: Constants (file paths), file_locks utility
- Used by: All routes and business logic

**Support Utilities:**
- **Auth** (`utils/auth.py`): User login, session management, decorators (`@require_auth`, `@require_owner`)
- **Config** (`utils/config.py`): Load/save `config.json`, integration credential retrieval (`_integ_val()`), tax rate helpers
- **Activity** (`utils/activity.py`): Append-only audit log to `activity_log.jsonl`, actor attribution
- **Constants** (`utils/constants.py`): All file paths, system prompt, default settings, environment variables
- **File Locks** (`utils/file_locks.py`): Cross-process safe file access via lock files in `.locks/` directory

**Bootstrap & Configuration:**
- Location: `app.py` (42 lines)
- Responsibilities: Flask app creation, blueprint registration, suppliers DB initialization, background daemon startup

## Data Flow

**Lead Capture & Nurturing:**

1. **Public API** — `/lead` POST endpoint (no auth) receives form data from chat interface
2. **Lead Creation** — Route handler validates, scores lead, appends to `leads.jsonl`
3. **Metadata Init** — Lead status + contact info stored in `lead_meta.json`
4. **Auto-Sequence Start** — `start_lead_nurture_sequence()` initializes timed campaign (5 steps over 28 days)
5. **Background Scheduler** — `_start_followup_scheduler()` daemon (runs every 10s) evaluates due steps, sends emails via SMTP
6. **Dashboard Update** — Frontend polls `/dashboard/api/leads` to display nurture progress

**Job Quote Follow-up:**

1. **Job Creation** — `/dashboard/api/jobs` POST creates job with status `"quoted"`
2. **Followup Sequence Start** — `start_followup_sequence()` creates campaign linked to job_id
3. **Status Tracking** — Campaign paused when job status changes to `"won"` or `"lost"`
4. **Email Rendering** — Template placeholders (e.g., `{client_name}`, `{quote_amount}`) merged with job data
5. **SMTP Send** — Daemon picks up due steps, sends via Gmail SMTP (credentials from config)

**Activity Logging:**

1. **All Mutations** — Every POST/PUT/DELETE route calls `log_activity(action, description, meta)`
2. **Actor Capture** — `get_current_user()` determines actor name (user or legacy "owner-jay")
3. **Append-Only** — Entry written to `activity_log.jsonl` with UUID, ISO timestamp, action, description
4. **Audit Trail** — `/dashboard/api/activity` returns last 50 entries sorted by timestamp DESC

**State Management:**
- **Leads** — All state in `lead_meta.json` (status, nurture tracking); history in `leads.jsonl` (immutable)
- **Jobs** — Single source `jobs.json`; followup state in `followups.json`; linked via `job_id`
- **Config** — Singleton `config.json` with company info, integrations, settings per role
- **Activity** — Append-only `activity_log.jsonl`; never modified after creation

## Key Abstractions

**Sequence Management:**
- Purpose: Automate multi-step email campaigns (leads or quotes) with configurable delays
- Examples: `utils/sequences.py` — functions `start_lead_nurture_sequence()`, `start_followup_sequence()`, `process_due_followups()`
- Pattern: Each sequence record holds job/lead ID, step index, due timestamp; daemon evaluates `(now >= due_ts)` and advances

**Email Templates:**
- Purpose: Personalize outgoing emails with lead/job/company data
- Examples: `_render_lead_template()`, `_render_template()`
- Pattern: Text placeholders replaced via `.replace()` calls; no template engine (Jinja2 not used)

**Configuration Overrides:**
- Purpose: Allow runtime config to override .env defaults for integration credentials
- Examples: `_integ_val("GMAIL_SENDER")` checks `config.json` first, then `.env`
- Pattern: Enables secure credential storage in dashboard settings without modifying .env

**File Locks:**
- Purpose: Prevent concurrent writes to JSON files (e.g., two routes saving invoices simultaneously)
- Examples: `utils/file_locks.py` creates `.locks/{filename}.lock` file; blocks until lock released
- Pattern: Context manager wraps all file I/O in data.py

**Permission Model:**
- Purpose: Role-based access control (owner/staff/accountant)
- Examples: `require_auth` checks session exists; `require_owner` checks role is owner/admin
- Pattern: User roles + granular permissions stored in `users.json`; dashboard reflects permissions in UI

## Entry Points

**Web Application:**
- Location: `app.py`
- Triggers: `python app.py` or `PORT=5001 python app.py`
- Responsibilities: Create Flask app, register 8 blueprints, init suppliers DB, start daemon threads

**Dashboard Page:**
- Location: `routes/dashboard.py` → `@dashboard_bp.route("/dashboard")`
- Triggers: GET `/dashboard` (no auth required, served to browser)
- Responsibilities: Render `templates/dashboard.html`

**Login Route:**
- Location: `routes/dashboard.py` → `@dashboard_bp.route("/dashboard/api/login", methods=["POST"])`
- Triggers: POST from login form with `username` + `password`
- Responsibilities: Check password hash, set session cookie, return user object

**Background Schedulers:**
- **Quote Follow-ups**: `_start_followup_scheduler()` (daemon thread) — checks every 10s for due steps, sends emails
- **Invoice Inbox**: `_start_invoice_poller()` (daemon thread) — polls Gmail IMAP every 60s for new vendor invoices

## Error Handling

**Strategy:** Route handlers return JSON responses with `{"ok": false, "error": "message"}` or HTTP status codes (401, 403, 400, 404).

**Patterns:**
- **Authentication** — `require_auth` decorator returns 401 if session missing; `require_owner` returns 403 if not owner
- **Data Validation** — Routes validate required fields (e.g., lead capture requires `name` OR `contact` OR `project_details`)
- **File I/O** — Data layer swallows exceptions from file_lock (e.g., if `.locks/` directory missing, retries are silent)
- **Email Sending** — SMTP errors logged to stdout; sequence continues if one step fails (graceful degradation)
- **Dashboard Fallback** — If activity log unreadable, `/dashboard/api/activity` returns `[]` instead of 500

## Cross-Cutting Concerns

**Logging:** No centralized logging framework; console output only (stdout for daemon threads). Activity audit trail captured via `log_activity()` function.

**Validation:** Each route validates its own input. No schema validation library; inline `if not x: return error()` checks.

**Authentication:** Session-based (Flask `session` dict). User ID stored in `session["user_id"]`. Legacy fallback: empty username + correct password authenticates as "owner-jay".

**Authorization:** Checked per-route via `@require_auth` and `@require_owner` decorators. Permissions stored in `users.json` and enforced in frontend UI (no server-side field masking).

---

*Architecture analysis: 2026-03-15*
