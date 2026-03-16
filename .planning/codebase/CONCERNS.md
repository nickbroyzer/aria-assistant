# Codebase Concerns

**Analysis Date:** 2025-03-15

## Tech Debt

**Unused Empty Database File:**
- Issue: `database.db` in root directory is created but never used (0 bytes). It appears to be a leftover from earlier development.
- Files: `/Users/nickbroyzer/Projects/my-assistant/database.db`
- Impact: Confusion about storage layer (JSON vs SQL); cleanup overhead; misleading to future developers about intended architecture
- Fix approach: Remove the file and document explicitly that this project uses JSON file storage + optional SQLite suppliers DB (via `utils/suppliers_db.py`)

**Print Statement Debugging Left In Code:**
- Issue: Multiple production files contain `print()` statements for debugging instead of structured logging
- Files: `utils/sequences.py`, `utils/invoice_inbox.py`, `routes/leads.py`, `routes/jobs.py`, and others
- Impact: No centralized logging, difficult to debug in production, logs scatter across stdout without timestamps or levels, no filtering capability
- Fix approach: Replace all `print()` calls with a logging module (Python's `logging` or structured logger). Example locations with print statements:
  - Line 92 in `utils/sequences.py`: `print(f"Lead nurture step {step_cfg['step']} sent to {email}")`
  - Line 115 in `utils/invoice_inbox.py`: `print(f"Invoice poller: {len(ids)} unseen emails")`
  - Lines 54, 230 in `utils/sequences.py` for Gmail connection failures

**Bare Exception Handlers:**
- Issue: Many routes and utilities catch all exceptions broadly without discrimination
- Files: `routes/jobs.py`, `routes/leads.py`, `routes/invoices.py`, `routes/chat.py`, `routes/dashboard.py`, `utils/invoice_inbox.py`
- Impact: Silent failures, difficult debugging, can mask unrelated errors, prevents proper error response differentiation
- Fix approach: Replace `except Exception as e:` with specific exception types. Example:
  - `routes/leads.py` line 105: catches all exceptions on lead save (should catch `IOError`, `json.JSONDecodeError` separately)
  - `utils/invoice_inbox.py` line 222: catches all IMAP/PDF parsing errors together
  - Add proper logging and return appropriate HTTP status codes (5xx for server errors, 4xx for client errors)

**Weak Authentication Check:**
- Issue: Auth decorator in `utils/auth.py` line 40 has a hardcoded magic user ID check: `session.get("user_id") != "owner-jay"`
- Files: `utils/auth.py` (line 40), `routes/` (all authenticated endpoints)
- Impact: Bypasses normal user lookup for one hardcoded user, creates security inconsistency, difficult to audit
- Fix approach: Remove hardcoded bypass; force all users through `get_current_user()` properly. Consider whether "owner-jay" session exists legitimately in `users.json` or if this is a fallback.

## Known Bugs

**Background Scheduler Thread Not Graceful:**
- Symptoms: `_start_followup_scheduler()` daemon thread runs infinite loop with broad exception catches; no way to stop cleanly; prints to stdout on error
- Files: `utils/sequences.py` lines 386-400
- Trigger: App startup; thread runs silently in background
- Workaround: Restart Flask app to stop background jobs
- Fix approach: Replace infinite loop with event-based scheduling (APScheduler library) or at least add proper logger, make thread non-daemon with shutdown hooks

**Invoice Poller Can Silently Fail:**
- Symptoms: `_start_invoice_poller()` catches all exceptions at line 244 and prints; no recovery mechanism; blocked emails stay marked as seen
- Files: `utils/invoice_inbox.py` lines 236-246
- Trigger: Network timeout, IMAP server down, invalid credentials
- Workaround: Check logs manually and restart
- Fix approach: Add retry logic with exponential backoff; use proper error tracking; persist unprocessed emails separately

**File Lock Timeout Silent Failure:**
- Symptoms: If a file lock times out (line 39 in `utils/file_locks.py`), the timeout exception is not caught in most read/write operations
- Files: `utils/file_locks.py`, all data operations in `utils/data.py`
- Trigger: Heavy concurrent load or disk I/O contention
- Workaround: Restart app
- Fix approach: Wrap all file lock operations with explicit timeout handling and user-facing error messages

**Date Parsing in Invoice Inbox Too Fragile:**
- Symptoms: `_parse_date()` in `utils/invoice_inbox.py` tries multiple date formats but returns today's date if none match (line 63), silently losing invoice date
- Files: `utils/invoice_inbox.py` lines 47-63
- Trigger: Invoice with unusual date format or OCR errors
- Workaround: Manual date entry in review queue
- Fix approach: Return `None` on parse failure and require manual date entry in the invoice review UI; don't silently substitute today

## Security Considerations

**Gmail Credentials in Configuration:**
- Risk: Gmail sender email and app password stored in `config.json` and readable by any code path
- Files: `utils/config.py` (loads `config.json`), used in `utils/sequences.py`, `utils/email.py`, `routes/leads.py`
- Current mitigation: `.env` file exists but passwords are also in JSON config; `.env` is in `.gitignore`
- Recommendations:
  - Move all secrets to `.env` only (never in JSON files committed to git)
  - Use `python-dotenv` to load from environment only
  - Add pre-commit hook to detect `GMAIL_APP_PASSWORD` or similar patterns in tracked files
  - Document that `.env` must be kept secure and never committed

**PDF Parsing from Untrusted Email:**
- Risk: `_parse_pdf_text()` in `utils/invoice_inbox.py` parses arbitrary PDFs from external emails without sandboxing
- Files: `utils/invoice_inbox.py` line 66-76
- Current mitigation: None
- Recommendations:
  - Limit PDF file size (e.g., max 10MB)
  - Use a sandboxed PDF parser or timeouts to prevent denial-of-service
  - Validate that the PDF doesn't contain suspicious embedded content
  - Consider processing PDFs in a separate subprocess with resource limits

**Session Secret Not Validated:**
- Risk: `app.secret_key` is required from `SECRET_KEY` env var but validation is loose (line 17-19 in `app.py`)
- Files: `app.py`
- Current mitigation: RuntimeError if missing
- Recommendations:
  - Verify secret key is at least 32 bytes long
  - Document that `SECRET_KEY` must be unique and strong in deployment

## Performance Bottlenecks

**No Pagination on Job/Invoice/Lead Lists:**
- Problem: All jobs, invoices, and leads are loaded entirely into memory and sent to frontend; no pagination
- Files: `routes/jobs.py` line 62, `routes/leads.py` line 265+, `routes/invoices.py`
- Cause: Simple `load_jobs()` returns all records; JSON-based storage doesn't scale
- Improvement path:
  - Implement server-side pagination in routes (limit=100, offset=0)
  - Add database indexing on created_at, status, job_number
  - Consider query filtering on backend before returning to frontend

**Email Sending Blocks Request Thread:**
- Problem: All email sends in routes (lead nurture, followup, notifications) are synchronous SMTP calls
- Files: `routes/leads.py` line 293+, `routes/jobs.py` line 506+, `utils/sequences.py` line 88
- Cause: Direct `smtplib.SMTP_SSL()` calls in request handler
- Improvement path:
  - Move email sends to task queue (Celery, RQ)
  - Use async/await if upgrading to async Flask
  - Log email job ID and return immediately; check status separately

**File Locking on Every Read:**
- Problem: Every `load_jobs()`, `load_leads()` call acquires a file lock, even for read-only access
- Files: `utils/data.py` (all load_* functions), `utils/file_locks.py`
- Cause: FileLock is writer-exclusive but blocks readers too
- Improvement path:
  - Implement read-write locks (readers don't block each other)
  - Cache frequently accessed data with TTL-based invalidation
  - Use SQLite with proper transaction isolation instead of JSON files

**Invoice Inbox Polls Every 30 Minutes Regardless of Utilization:**
- Problem: IMAP poller wakes up and connects every 30 minutes even if no new emails
- Files: `utils/invoice_inbox.py` line 240 (hardcoded 1800 second sleep)
- Cause: Simple time-based scheduler
- Improvement path:
  - Use push notifications (Gmail push API) instead of polling
  - Implement exponential backoff if no emails found
  - Add manual "Check Now" button for urgent cases

## Fragile Areas

**Followup/Nurture Sequence State Machine:**
- Files: `utils/sequences.py`, `followups.json`, `lead_nurtures.json`
- Why fragile:
  - Status field can be "active", "stopped", "completed", "paused" with no enum validation
  - Transitions don't validate: can go from "completed" back to "active" if modified manually
  - No rollback if email send fails mid-step
  - JSON file could be corrupted by external process
- Safe modification:
  - Add `Enum` for valid statuses in Python
  - Add state transition validation before status updates
  - Wrap step sends in database transaction (if moving to SQLite)
  - Add JSON schema validation on load

**Job Status Field:**
- Files: `routes/jobs.py`, `jobs.json`
- Why fragile: Status can be any string ("quoted", "in_progress", "completed", "on_hold", etc.) with no enforcement
- Safe modification:
  - Define enum of valid job statuses in `utils/constants.py`
  - Validate status transitions (e.g., can't go from "completed" to "quoted")
  - Write migration script to standardize existing job statuses
  - Add validation in PUT endpoint

**Lead Score Calculation:**
- Files: `utils/email.py` lines 22-56
- Why fragile: Score logic is hardcoded magic numbers (score += 2, 3, etc.) with no justification
- Safe modification:
  - Extract scoring weights to configuration
  - Add unit tests for edge cases (empty project details, no contact info)
  - Document why each signal contributes points

**Email Template Rendering:**
- Files: `utils/sequences.py` line 36-46 (lead nurture), line 212-222 (followup), `routes/leads.py` line 294+
- Why fragile: Simple `.replace()` calls can fail silently if template variables are None or missing; no escaping for HTML injection
- Safe modification:
  - Use Jinja2 template engine with strict undefined handling
  - Escape all user-supplied values when rendering HTML emails
  - Add tests for missing/null substitution variables

## Scaling Limits

**JSON File Storage:**
- Current capacity: Single-file operations can handle ~10k-100k records before noticeable slowdown
- Limit: File locking prevents concurrent writes; large files slow to parse/serialize; no query filtering on backend
- Scaling path:
  - Migrate to SQLite (suppliers.db pattern already exists) for all entities
  - Implement proper indexes on frequently queried fields
  - Add read-replica caching layer
  - If >1M records, consider PostgreSQL + connection pooling

**Email Sending Rate:**
- Current capacity: Limited by Gmail App Password rate limits (~50 emails per hour per account)
- Limit: Background scheduler sends synchronously one at a time; no batch sending
- Scaling path:
  - Use SendGrid or Amazon SES for higher throughput
  - Implement queue-based sending with rate limiting config
  - Support multiple sender addresses

**Background Thread Reliability:**
- Current capacity: Single daemon thread for both followups and lead nurtures
- Limit: If one process crashes, both pause; no persistence of scheduler state; no inter-worker coordination
- Scaling path:
  - Replace with proper job queue (RQ, Celery)
  - Persist scheduled job state in database
  - Add monitoring/alerting for task failures

## Dependencies at Risk

**pdfplumber Without Validation:**
- Risk: Arbitrary PDF parsing from external emails; no bounds checking on file size or page count
- Impact: Large or malicious PDFs could cause DoS or memory exhaustion
- Migration plan:
  - Add file size limits before PDF parsing (max 10MB)
  - Add page count limits (max 100 pages)
  - Consider pypdf2 or pdfminer as alternatives with better error handling
  - Add timeout wrapper around PDF parsing

**filelock Library Timeout:**
- Risk: Uses `FileLock` with hardcoded 10-second timeout; if exceeded, exception crashes the operation
- Impact: High-contention environments will fail writes unpredictably
- Migration plan:
  - Move to SQLite with proper transaction isolation (no file locks needed)
  - If staying with JSON, increase timeout and add exponential backoff retry

**Flask Debug Mode:**
- Risk: `app.config['TEMPLATES_AUTO_RELOAD'] = True` is development-only feature; if `debug=True` in production, templates reload on every request
- Impact: Performance degradation, potential for unintended template changes
- Migration plan:
  - Remove or make environment-dependent: `app.config['TEMPLATES_AUTO_RELOAD'] = os.getenv('ENV') == 'development'`
  - Run production with `debug=False`

## Missing Critical Features

**No Activity Audit for Data Modifications:**
- Problem: `activity_log.jsonl` logs user actions but not what actually changed (amounts, statuses, fields). The "What Changed" table in UI is manually constructed and unreliable.
- Blocks: Cannot audit trail cost changes, cannot detect unauthorized modifications
- Fix approach:
  - Wrap all save operations with before/after state comparison
  - Store delta (old vs new field values) in activity log
  - Add audit-specific schema for changes

**No Validation of Invoice Data Consistency:**
- Problem: Job cost records have no foreign key validation; can reference deleted jobs
- Blocks: Data integrity after job deletion; orphaned cost records
- Fix approach:
  - If staying with JSON: validate all job references before save
  - If moving to SQLite: add foreign key constraints and cascading rules

**No Backup/Recovery Mechanism:**
- Problem: JSON files are the single source of truth; if corrupted, no recovery
- Blocks: Cannot restore from accidental deletions, no disaster recovery
- Fix approach:
  - Implement daily backup to S3 or external storage
  - Add JSON schema validation on load with recovery from backup if invalid
  - Version control critical files in git with automatic commits

**No Email Delivery Confirmation:**
- Problem: Emails are marked "sent" immediately; if Gmail SMTP fails, no retry or notification
- Blocks: Cannot track which emails actually delivered
- Fix approach:
  - Query Gmail API to check sent folder
  - Or use webhook-based email service (SendGrid) with delivery tracking
  - Add delivery status field to lead_comms and job_comms

## Test Coverage Gaps

**No Unit Tests:**
- What's not tested: Virtually none of the business logic has unit tests (lead scoring, email templating, state transitions)
- Files: `utils/email.py` (score_lead), `utils/sequences.py` (template rendering), `routes/leads.py` (lead validation)
- Risk: Refactoring breaks scoring without detection; email templates silently fail on edge cases
- Priority: High — add tests for lead scoring, email rendering, state machine transitions before refactoring

**No Integration Tests:**
- What's not tested: End-to-end flows (capture lead → auto-nurture → convert to job) are not validated
- Files: All route files, sequences, email sends
- Risk: Changes to data flow silently break automation
- Priority: High — add tests for lead-to-job conversion flow, nurture sequence delivery

**No IMAP Mocking:**
- What's not tested: Invoice inbox polling logic cannot be tested without real Gmail account
- Files: `utils/invoice_inbox.py` (poll_invoice_inbox)
- Risk: Regressions in parsing, rate limiting, or error handling go undetected
- Priority: Medium — mock IMAP server for invoice parsing tests

**No Error Path Testing:**
- What's not tested: No tests for file lock timeout, SMTP failure, JSON corruption recovery
- Files: `utils/data.py`, `utils/sequences.py`
- Risk: Error conditions behave unpredictably
- Priority: Medium — add tests for missing credentials, network failures

---

*Concerns audit: 2025-03-15*
