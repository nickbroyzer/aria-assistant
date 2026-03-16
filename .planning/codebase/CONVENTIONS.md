# Coding Conventions

**Analysis Date:** 2026-03-15

## Naming Patterns

**Files:**
- Python modules: `snake_case.py` (e.g., `auth.py`, `file_locks.py`, `sequences.py`)
- Routes blueprints: Named explicitly with `_bp` suffix (e.g., `jobs_bp`, `leads_bp`, `invoices_bp`)
- Constants file: `constants.py` for all environment and system defaults

**Functions:**
- Public functions: `snake_case` (e.g., `load_jobs()`, `save_invoices()`)
- Private/internal functions: Leading underscore prefix (e.g., `_render_template()`, `_send_lead_nurture_step()`, `_integ_val()`)
- Async HTTP handlers: Named to indicate action (e.g., `api_start_followup()`, `send_test_followup()`)
- Getter decorators: `@require_auth`, `@require_owner` (not `@login_required`)

**Variables:**
- Local variables: `snake_case` (e.g., `inv_id`, `job_id`, `line_items`)
- Boolean flags: Descriptive names with verb prefixes (e.g., `apply_tax`, `is_active`)
- Dictionary access: Direct key strings for JSON data (e.g., `job.get("job_id")`)

**Types:**
- No type hints in function signatures (Python codebase uses dynamic typing)
- Class attributes: Descriptive names matching JSON keys

## Code Style

**Formatting:**
- No explicit formatter configured (.black, .prettierrc not found)
- Python: 4-space indentation (standard Python convention)
- Line lengths: Generally under 100 characters, some longer docstrings accepted
- Import organization: `import` statements first, then `from` imports

**Linting:**
- No linter configuration detected (.flake8, .pylintrc not found)
- Code follows PEP 8 conventions informally

**Comments:**
- Module docstrings: Triple-quoted strings at file top describing blueprint/purpose
- Route documentation: Inline docstrings listing endpoints and HTTP methods
- Section headers: ASCII art dividers for logical sections (e.g., `# ── Jobs CRUD ────────`)
- Function docstrings: Present for complex functions, parameters sometimes documented

**Whitespace:**
- Blank lines separate logical sections within files
- Two blank lines between top-level definitions

## Import Organization

**Order:**
1. Standard library imports (json, os, datetime, etc.)
2. Third-party imports (flask, dotenv, google libraries, etc.)
3. Local utility imports from utils/
4. Route blueprint definitions

**Path Aliases:**
- No path aliases configured
- Imports use relative paths: `from utils.auth import get_current_user`
- Blueprint imports: `from routes.jobs import jobs_bp`

**Example from `routes/jobs.py`:**
```python
import os
import re
import smtplib
import uuid
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from flask import Blueprint, jsonify, request, send_from_directory

from utils.constants import DEFAULT_SETTINGS
from utils.config import _integ_val, load_config, safe_float
from utils.auth import get_current_user, load_users, require_auth
```

## Error Handling

**Patterns:**
- Try/except blocks for integrations and external I/O (Gmail, file parsing, HTTP requests)
- Silent catch with logging: `except Exception as e: print(f"...failed: {e}")`
- API errors: Return jsonify with error message and HTTP status code
- File operations: All file I/O wrapped in `file_lock()` context manager
- Silent fallback: Many operations continue on error without breaking (e.g., Sheets logging, activity logging)

**Examples:**

```python
# routes/jobs.py
try:
    msg = MIMEMultipart("alternative")
    # ... send email ...
except Exception as e:
    print(f"Send email failed: {e}")
    return jsonify({"ok": False, "error": "Email send failed"}), 500

# utils/data.py - leads append with Sheets webhook
try:
    requests.post(SHEETS_WEBHOOK, json=sheets_data, timeout=10)
except Exception as e:
    print(f"Sheets logging failed: {e}")
    # continue anyway

# utils/sequences.py
try:
    msg = MIMEMultipart("alternative")
    # ...
except Exception as e:
    print(f"Nurture email failed: {e}")
    return False
```

**Validation:**
- Request data: Direct `request.get_json() or {}` with `.get()` for keys
- Safe float conversion: `safe_float(val, default=0.0)` utility
- Required fields: Checked explicitly before use (e.g., `if not to_email: return 400`)

## Logging

**Framework:** `print()` statements for diagnostics (no logging library)

**Patterns:**
- Print only on errors: `print(f"... failed: {e}")`
- Activity logging: `log_activity(action, description, meta)` function in `utils.activity`
- Silent operations: Most background tasks (sequence processing) fail silently

**Example:**
```python
# utils/activity.py
def log_activity(action: str, description: str, meta: dict = None):
    """Append a timestamped activity event to the activity log."""
    user = get_current_user()
    actor = user.get("name") or user.get("username") or "Unknown"
    entry = {
        "id": str(uuid.uuid4()),
        "ts": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "description": description,
        "actor": actor,
        "meta": meta or {}
    }
    try:
        with file_lock(ACTIVITY_FILE):
            with open(ACTIVITY_FILE, "a") as f:
                f.write(json.dumps(entry) + "\n")
    except Exception:
        pass  # Silent fail for audit trail
```

## Module Design

**Exports:**
- Utilities export multiple related functions: `load_jobs()`, `save_jobs()`, `next_job_number()`
- Blueprint modules: Single blueprint instance `jobs_bp` exported, routes registered via decorator
- No class-based views (all function-based routes)

**Barrel Files:**
- `routes/__init__.py`: Central registry of all blueprints with `register_blueprints(app)` function
- No wildcard exports; explicit imports

**Data Layer Pattern:**
- Each entity (jobs, invoices, leads, etc.) has load/save functions
- File locking on all data access: `with file_lock(JOBS_FILE): ...`
- Consistent JSON serialization: `json.dump(data, f, indent=2, default=str)`

**Example from `routes/__init__.py`:**
```python
from routes.ash import ash_bp
from routes.chat import chat_bp
from routes.dashboard import dashboard_bp

ALL_BLUEPRINTS = [ash_bp, chat_bp, dashboard_bp, ...]

def register_blueprints(app):
    for bp in ALL_BLUEPRINTS:
        app.register_blueprint(bp)
```

## Function Design

**Size:**
- Most functions 15-50 lines
- Longer functions for complex workflows (email templating, sequence processing)
- One responsibility per function

**Parameters:**
- Direct parameter passing over dependency injection
- Request context accessed via `request.get_json()`, `session.get()`
- Configuration loaded via `load_config()` calls

**Return Values:**
- API routes: `jsonify(dict)` or `jsonify(dict), status_code`
- Data functions: Return loaded data or empty list/dict
- Background workers: Return boolean or None

**Example:**
```python
@jobs_bp.route("/dashboard/api/followups/start", methods=["POST"])
@require_auth
def api_start_followup():
    data = request.json or {}
    job_id = data.get("job_id", "")
    jobs = load_jobs()
    job = next((j for j in jobs if j["job_id"] == job_id), None)
    if not job:
        return jsonify({"ok": False, "error": "Job not found"}), 404
    # ... process ...
    return jsonify({"ok": True})
```

## Frontend JavaScript (dashboard.html)

**Naming:**
- Global page functions: `function loadMissionControl()`, `function showPage(page)`
- Event handlers: Named descriptively (e.g., `function initCurrencyInput(el)`, `async function checkPassword()`)
- Helper functions: Lowercase prefixed (e.g., `function formatCurrency(n)`, `function renderLeads()`)

**Style:**
- Inline event handlers in HTML: `onclick="checkPassword()"`
- No framework (vanilla JavaScript)
- CSS variables for theming: `--orange`, `--surface`, `--text`, etc.

**Patterns:**
- Fetch with `fetch()` + `.json()` chaining
- Global state: `allJobs`, `allLeads`, `allInvoices` arrays populated on page load
- DOM manipulation: Direct `document.getElementById()`, `classList.add/remove()`
- Event delegation: Direct element queries, not event listeners on document

**Example:**
```javascript
async function loadMissionControl() {
    const jobs = await (await fetch("/dashboard/api/jobs")).json();
    const leads = await (await fetch("/dashboard/api/leads")).json();
    // ... render to DOM ...
}

function showPage(page) {
    document.querySelectorAll('[id^="page-"]').forEach(el => el.style.display = 'none');
    const pageEl = document.getElementById(`page-${page}`);
    if (pageEl) pageEl.style.display = 'block';
}
```

## Passwords and Secrets

**Storage:**
- Environment variables: `.env` file (git-ignored)
- Config-based override: `config.json` can store integration credentials (non-database)
- Helper: `_integ_val(key)` prefers config.json, falls back to env var

**Example:**
```python
# utils/config.py
def _integ_val(key):
    """Return integration credential: config.json overrides .env."""
    cfg = load_config().get("integrations", {})
    return cfg.get(key) or os.getenv(key, "")

# Usage
sender = _integ_val("GMAIL_SENDER")
pw = _integ_val("GMAIL_APP_PASSWORD")
```

## Concurrency & State Management

**File Locking:**
- All data access uses `file_lock()` from `utils/file_locks.py`
- Cross-process safe via `filelock` library (works with gunicorn workers)
- Per-file locks cached in memory: `_locks: dict[str, FileLock] = {}`

**Background Tasks:**
- Daemon threads started on app init: `_start_followup_scheduler()`, `_start_invoice_poller()`
- Threads check for work at intervals (sleep-based polling)
- Silent errors; no exception propagation from workers

**Session Management:**
- Flask `session` object for user auth: `session.get("user_id")`
- Current user lookup: `get_current_user()` queries users.json for matching user_id

## API Response Format

**Success:**
```json
{"ok": true, "data": {...}}
or
{"key": "value", ...}  (direct object)
```

**Error:**
```json
{"ok": false, "error": "Error message"}
or
{"error": "Error message"}
```

**HTTP Status Codes:**
- 200: Success
- 201: Created
- 400: Bad request (validation, missing fields)
- 401: Unauthorized (no session)
- 403: Forbidden (insufficient permissions)
- 404: Not found (resource not found)
- 500: Server error (exception in handler)

---

*Convention analysis: 2026-03-15*
