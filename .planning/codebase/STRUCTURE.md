# Codebase Structure

**Analysis Date:** 2026-03-15

## Directory Layout

```
/Users/nickbroyzer/Projects/my-assistant/
├── app.py                          # Flask app bootstrap, blueprint registration, daemon startup
├── routes/                         # HTTP route blueprints organized by domain
│   ├── __init__.py                 # Blueprint discovery and registration
│   ├── ash.py                      # Chat/AI assistant routes
│   ├── chat.py                     # Chat interface (Anthropic Claude integration)
│   ├── dashboard.py                # Auth, settings, users, activity, stats
│   ├── invoices.py                 # Invoice CRUD, vendor invoices
│   ├── jobs.py                     # Job CRUD, job costs, followup sequences
│   ├── leads.py                    # Lead capture, nurture sequences, comms
│   ├── payroll.py                  # Payroll records
│   └── suppliers.py                # Supplier/vendor management
├── utils/                          # Shared business logic and data helpers
│   ├── __init__.py
│   ├── activity.py                 # Activity audit log (append-only to activity_log.jsonl)
│   ├── ash_scanner.py              # Gmail inbox scanner for assistant
│   ├── auth.py                     # User login, session, @require_auth decorator
│   ├── calendar.py                 # Google Calendar API integration
│   ├── config.py                   # Load/save config.json, integration creds
│   ├── constants.py                # All file paths, defaults, system prompt, env vars
│   ├── data.py                     # Load/save JSON/JSONL for all entities
│   ├── email.py                    # Lead scoring, email sending, comm logging
│   ├── file_locks.py               # Cross-process file locking
│   ├── gmail_auth.py               # Gmail OAuth token management
│   ├── html_generators.py          # HTML email templates
│   ├── invoice_inbox.py            # Gmail IMAP polling for vendor invoices
│   ├── memory.py                   # Chat memory management
│   ├── search.py                   # Job/lead search helpers
│   ├── seed_orders.py              # Test data generation
│   ├── sequences.py                # Lead/quote nurture automation, scheduler daemon
│   ├── suppliers_db.py             # Supplier database schema and initialization
│   └── data/                       # Generated/cached data (not committed)
├── templates/                      # Jinja2 templates
│   ├── dashboard.html              # Single-page app (all UI in one file)
│   ├── index.html                  # Legacy/alternative UI
│   └── widget.html                 # Embedded widget for external sites
├── static/                         # Static assets (images, minimal JS)
│   ├── widget.js                   # Embed script for external sites
│   └── *.png                       # Screenshots (development artifacts)
├── job_files/                      # Job document storage (UUID directories, user-uploaded files)
├── .locks/                         # File-lock lock files (created at runtime)
├── .planning/                      # GSD planning documents
│   └── codebase/                   # Architecture/structure analysis
├── .env                            # Environment variables (secret, not committed)
├── config.json                     # Runtime config (company, integrations, settings)
├── leads.jsonl                     # Append-only lead records
├── lead_meta.json                  # Lead status, nurture state, contact metadata
├── lead_comms.json                 # Lead communication history
├── job_comms.json                  # Job communication history
├── jobs.json                       # Job records
├── invoices.json                   # Invoice records
├── jobcosts.json                   # Job cost line items
├── vendorinvoices.json             # Vendor invoice records
├── people.json                     # Staff/subcontractor records
├── payroll.json                    # Payroll records
├── users.json                      # User accounts (password hashes, roles, permissions)
├── appointments.json               # Google Calendar appointments cache
├── followups.json                  # Quote follow-up campaign state
├── lead_nurtures.json              # Lead nurture campaign state
├── invoice_inbox.json              # Automated invoice inbox queue (IMAP polling)
├── activity_log.jsonl              # Audit trail (append-only)
├── google_token.json               # Google Calendar OAuth token
├── google_credentials.json         # Google Calendar API credentials
├── gmail_token.json                # Gmail IMAP OAuth token
├── gmail_credentials.json          # Gmail API credentials
└── venv/                           # Python virtual environment (not committed)
```

## Directory Purposes

**routes/**
- Purpose: Flask blueprints for all HTTP endpoints
- Contains: Blueprint definitions with route handlers, request validation, response formatting
- Key files: `dashboard.py` (auth, settings), `jobs.py` (job CRUD + sequences), `leads.py` (lead capture + nurture), `invoices.py` (invoice management)

**utils/**
- Purpose: Shared libraries, data access layer, business logic, integrations
- Contains: Data I/O, email/calendar/Gmail APIs, authentication, configuration, sequences automation
- Key files: `data.py` (all file I/O), `sequences.py` (background daemon), `config.py` (settings), `auth.py` (login)

**templates/**
- Purpose: Server-rendered HTML
- Contains: Single-page app with embedded JavaScript (no build step, vanilla fetch API)
- Key files: `dashboard.html` (main UI, 623KB), `widget.html` (external embed)

**static/**
- Purpose: Static assets served by Flask
- Contains: Images, embed script, development screenshots
- Key files: `widget.js` (embed functionality)

**job_files/**
- Purpose: User-uploaded documents per job
- Contains: Directory per job (UUID), files within
- Generated: Yes, at runtime when files uploaded
- Committed: No

**.locks/**
- Purpose: File-lock synchronization primitives
- Contains: `.lock` files created/released during data I/O
- Generated: Yes, at runtime during concurrent file access
- Committed: No

## Key File Locations

**Entry Points:**
- `app.py`: Flask app start, blueprint registration, daemon threads
- `routes/__init__.py`: Blueprint discovery via `register_blueprints(app)`
- `templates/dashboard.html`: Single-page application (loaded by `/dashboard` route)

**Configuration:**
- `config.json`: Runtime settings (company, integrations, role permissions)
- `.env`: Environment variables (secrets, Gmail credentials, master password)
- `utils/constants.py`: All file paths, defaults, system prompt, environment variable names

**Core Logic:**
- `routes/dashboard.py`: Authentication, user management, settings UI
- `routes/jobs.py`: Job CRUD, quote follow-up sequences, job costs
- `routes/leads.py`: Lead capture, lead nurture sequences, scoring
- `utils/sequences.py`: Automated email campaign scheduler (background daemon)
- `utils/email.py`: Email sending, lead scoring, communication logging
- `utils/data.py`: All persistent storage load/save operations

**Testing & Development:**
- `seed_jobcosts.py`: Generate test job cost data
- `seed_vendor_invoices.py`: Generate test vendor invoices
- `seed_employee_payroll.py`: Generate test payroll records
- `seed_office_staff.py`: Generate test staff records
- `seed_lead_phones.py`: Add phone numbers to existing leads

## Naming Conventions

**Files:**
- Route files: `routes/{domain}.py` — lowercase, domain-specific (e.g., `jobs.py`, `leads.py`)
- Utility files: `utils/{purpose}.py` — lowercase, purpose-specific (e.g., `sequences.py`, `email.py`)
- Data files: `{entity}.json` or `{entity}.jsonl` — plural noun (e.g., `jobs.json`, `leads.jsonl`)
- Metadata files: `{entity}_meta.json` — lowercase with `_meta` suffix (e.g., `lead_meta.json`)
- Lock files: `.locks/{filename}.lock` — hidden directory, lock suffix

**Directories:**
- `job_files/{job_id}/` — UUID-named directory per job
- `utils/data/` — Generated/cached data (not version-controlled)

**Python Functions/Classes:**
- Data loaders: `load_{entity}()` (e.g., `load_jobs()`, `load_leads()`)
- Data savers: `save_{entity}()` (e.g., `save_jobs()`, `save_leads()`)
- Generators: `next_{entity}_number()` (e.g., `next_job_number()`, `next_invoice_number()`)
- Decorators: `@{permission}` (e.g., `@require_auth`, `@require_owner`)
- Utilities: `_{purpose}()` (leading underscore for internal helpers, e.g., `_integ_val()`, `_render_template()`)

## Where to Add New Code

**New Feature (e.g., proposal management):**
- Primary code: `routes/proposals.py` (new blueprint with CRUD endpoints)
- Tests: N/A (no test files committed)
- Data access: Add load/save functions to `utils/data.py`
- Config: Add settings section to `DEFAULT_SETTINGS` in `utils/constants.py`
- Frontend: Add page and routes to `templates/dashboard.html`

**New Route Endpoint:**
1. Add function to appropriate route file (e.g., `routes/jobs.py`)
2. Decorate with `@blueprint.route("/path", methods=["GET|POST|PUT|DELETE"])`
3. Add `@require_auth` or `@require_owner` for access control
4. Validate input, call data layer functions, log activity, return JSON
5. Register blueprint (already done in `routes/__init__.py` if creating new module)

**New Data Entity:**
1. Add file path constant to `utils/constants.py` (e.g., `PROPOSALS_FILE = "proposals.json"`)
2. Add load/save functions to `utils/data.py`
3. Create route endpoints in appropriate blueprint
4. Add default settings to `DEFAULT_SETTINGS` in `constants.py` if configurable
5. Add to activity logging for mutations

**New Utility Function:**
- Shared across routes: Add to appropriate `utils/{purpose}.py` file
- Email-related: `utils/email.py`
- Sequences/automation: `utils/sequences.py`
- Configuration: `utils/config.py`
- Data I/O: `utils/data.py`

**New Integration (e.g., QuickBooks):**
1. Create integration module: `utils/quickbooks.py` with auth and API wrappers
2. Add credentials to `config.json` via Settings → Integrations UI
3. Add integration test/toggle in `routes/dashboard.py` settings endpoints
4. Add environment variable names to `utils/constants.py`
5. Use `_integ_val(key)` to retrieve credentials at runtime

## Special Directories

**.locks/**
- Purpose: File-lock primitives for concurrent access control
- Generated: Yes, at runtime during data I/O
- Committed: No (in .gitignore)
- Cleanup: Locks expire/cleanup automatically; safe to delete if orphaned

**.planning/**
- Purpose: GSD codebase analysis and phase planning
- Generated: Yes, by GSD mappers and planners
- Committed: Yes (tracking decisions)
- Structure: `codebase/` for analysis (ARCHITECTURE.md, STRUCTURE.md, etc.)

**.claude/worktrees/**
- Purpose: Claude Code worktrees for isolated editing sessions
- Generated: Yes, automatically by Claude Code
- Committed: No (in .gitignore)

**job_files/**
- Purpose: Per-job document storage (user uploads, generated estimates, etc.)
- Generated: Yes, at runtime when files uploaded
- Committed: No (in .gitignore)
- Subdirectories: One UUID-named directory per job, files within

---

*Structure analysis: 2026-03-15*
