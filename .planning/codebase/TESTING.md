# Testing Patterns

**Analysis Date:** 2026-03-15

## Test Framework

**Runner:**
- Not currently installed
- Codebase has no test suite

**Assertion Library:**
- Not applicable — no testing framework present

**Run Commands:**
```bash
# No test commands defined
# Manual testing via live server and API endpoints
```

## Current Testing Approach

**Manual Testing:**
This codebase relies on **manual testing through live Flask endpoints**. There are no automated unit or integration tests.

**Test Email Endpoints:**
The only built-in "test" features are manual email preview endpoints:
- `POST /dashboard/api/followups/send-test` — Preview quote follow-up email template
- `POST /dashboard/api/lead-nurtures/send-test` — Preview lead nurture email template

These endpoints:
- Accept step number, email address, and optional overrides
- Render email subject and body using template variables
- Send test email with `[TEST — Step N]` prefix to indicate it's a test
- Include preview HTML showing what the recipient will see

Example from `routes/jobs.py`:
```python
@jobs_bp.route("/dashboard/api/followups/send-test", methods=["POST"])
@require_auth
def send_test_followup():
    """Send a test email preview for a quote follow-up step."""
    data = request.json or {}
    step = data.get("step", 1)
    to_email = data.get("email", "")
    subject = data.get("subject", "Test Email")

    # ... render template ...
    msg["Subject"] = f"[TEST — {label}] {rendered_subject}"
    # ... send via SMTP ...
```

## TESTING Environment Flag

**App Configuration:**
`app.py` checks for a TESTING flag to disable background threads on startup:

```python
# app.py
if not app.config.get("TESTING") and os.getenv("TESTING") != "1":
    _start_followup_scheduler()
    _start_invoice_poller()
```

**Use Case:**
Set `TESTING=1` as environment variable to prevent background daemon threads (quote follow-up scheduler, invoice poller) from running during test/development.

## Data Fixtures & Test Data

**Seed Scripts:**
Several seed scripts exist for populating test data:
- `seed_historical_jobs.py` — Generate historical jobs with various statuses
- `seed_jobcosts.py` — Generate job cost records
- `seed_lead_emails.py` — Generate lead history with email interactions
- `seed_lead_comms.py` — Generate lead communications log
- `seed_orders.py` — Generate supplier orders

**Test Data Filtering:**
- `seed_lead_comms.py` skips test leads: `SKIP_NAMES = {"test user", "test customer", "test lead", ""}`
- Other scripts filter out test entries to avoid polluting real data

**Running Seed Scripts:**
```bash
python seed_historical_jobs.py
python seed_jobcosts.py
python seed_lead_emails.py
```

These are manual development utilities, not automated test fixtures.

## File-Based Test Isolation

**JSON Data Storage:**
Data is stored in JSON/JSONL files with file-level locks via `utils/file_locks.py`:

```python
# utils/data.py - Example pattern
def load_jobs():
    if os.path.exists(JOBS_FILE):
        with file_lock(JOBS_FILE):  # Cross-process safe
            with open(JOBS_FILE) as f:
                return json.load(f)
    return []
```

**Testing Implication:**
- No database transactions or rollback capability
- Manual cleanup of JSON files required after testing
- File locks prevent concurrent writes but don't provide test isolation
- Each test would need to:
  1. Backup existing JSON files
  2. Create fresh test data
  3. Run test
  4. Restore original files

## No Mocking Framework

**Current State:**
- No mocking library installed (no `unittest.mock`, `pytest-mock`, etc.)
- Integration tests are manual via live endpoints
- Email sending is real: Uses SMTP to send actual test emails (marked `[TEST — ...]`)

**What Would Need Mocking:**
- `smtplib` for email operations (currently sends real emails)
- `requests` for external APIs (Google Calendar, Sheets webhook, Gmail API)
- File I/O and file locking (currently real)
- Background thread operations (schedulers, pollers)

## Test Coverage

**Requirements:**
- No coverage target enforced
- No coverage measurement tool installed

**Areas Without Tests:**
All production code:
- `routes/` — All Flask route handlers (jobs, leads, invoices, etc.)
- `utils/` — All utility functions (data I/O, email, sequences, etc.)
- `app.py` — Application initialization and configuration

**High-Risk Untested Areas:**
- Email template rendering (`_render_lead_template()`, `_render_followup_template()`)
- File locking and concurrent data access
- Background scheduler threads (`_start_followup_scheduler()`, `_start_invoice_poller()`)
- Gmail OAuth flow and token management
- PDF invoice parsing and vendor extraction
- Lead scoring algorithm (`score_lead()`)
- Lead status transitions and nurture sequence logic

## Common Testing Needs (If Tests Were Written)

**What to Test:**
- Data loading/saving operations with file locks
- Lead scoring accuracy
- Email template variable substitution
- Job cost calculations and invoice totals
- Lead status state machine (new → contacted → qualified → converted/lost)
- Permission checks (`@require_auth`, `@require_owner`)
- API request validation (required fields, type checks)

**Test Structure Pattern (if implemented):**
Based on code organization, tests would likely be:
- Placed in `tests/` or `test_` prefixed in each module
- Named `test_*.py` following Python convention
- Using `pytest` (modern Flask standard) or `unittest`
- Testing each route blueprint independently
- Using fixtures for:
  - Fresh test JSON files
  - Mock SMTP/Google services
  - Authenticated session setup

**Example Test Structure (hypothetical):**
```python
# tests/test_leads.py (not currently present)
import pytest
from flask import Flask
from routes.leads import leads_bp

@pytest.fixture
def app():
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.register_blueprint(leads_bp)
    return app

@pytest.fixture
def client(app):
    return app.test_client()

def test_capture_lead_requires_contact_info(client):
    """POST /lead with no contact info should return 400"""
    resp = client.post('/lead', json={})
    assert resp.status_code == 400
```

## Static Analysis & Linting

**Current State:**
- No linter configured (.flake8, .pylintrc not found)
- No formatter configured (.black, Ruff not found)
- Code follows PEP 8 informally

**If Linting Were Added:**
- Would catch syntax errors, unused imports, naming violations
- Could enforce code style consistency
- Useful addition before adding automated tests

## Deployment Testing

**Manual Verification:**
- Live server testing at `http://localhost:5001/dashboard`
- Manual user acceptance testing (QA by developer)
- No staging environment or automated deployment tests

**Production Risk:**
Without automated tests, production relies on:
- Manual testing before deployment
- Small incremental changes
- Developer familiarity with code paths
- File locking for data consistency (limited protection)

---

*Testing analysis: 2026-03-15*
