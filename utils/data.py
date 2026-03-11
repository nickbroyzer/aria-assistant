"""
Data I/O for all JSON/JSONL entity files.

Every load/save function uses file_lock for cross-process safety.
"""

import json
import os
import requests
from datetime import datetime

from utils.constants import (
    JOBS_FILE, INVOICES_FILE, JOBCOSTS_FILE, PEOPLE_FILE,
    PAYROLL_FILE, FOLLOWUPS_FILE, LEADS_FILE, LEAD_META_FILE,
    LEAD_NURTURES_FILE, LEAD_COMMS_FILE, JOB_COMMS_FILE,
    VENDOR_INVOICES_FILE, INVOICE_INBOX_FILE, SHEETS_WEBHOOK,
)
from utils.file_locks import file_lock


# ── Jobs ──────────────────────────────────────────────────────────────────────
def load_jobs():
    if os.path.exists(JOBS_FILE):
        with file_lock(JOBS_FILE):
            with open(JOBS_FILE) as f:
                return json.load(f)
    return []

def save_jobs(data):
    with file_lock(JOBS_FILE):
        with open(JOBS_FILE, "w") as f:
            json.dump(data, f, indent=2, default=str)

def next_job_number():
    jobs = load_jobs()
    year = datetime.now().year
    nums = [int(j.get("job_number", "0").split("-")[-1]) for j in jobs
            if str(year) in j.get("job_number", "")]
    return f"JOB-{year}-{str(max(nums) + 1 if nums else 1).zfill(3)}"


# ── Invoices ──────────────────────────────────────────────────────────────────
def load_invoices():
    if os.path.exists(INVOICES_FILE):
        with file_lock(INVOICES_FILE):
            with open(INVOICES_FILE) as f:
                return json.load(f)
    return []

def save_invoices(data):
    with file_lock(INVOICES_FILE):
        with open(INVOICES_FILE, "w") as f:
            json.dump(data, f, indent=2, default=str)

def next_invoice_number():
    invoices = load_invoices()
    year = datetime.now().year
    nums = [int(i.get("invoice_number", "0").split("-")[-1]) for i in invoices
            if str(year) in i.get("invoice_number", "")]
    return f"{year}-{str(max(nums) + 1 if nums else 1).zfill(3)}"


# ── People ────────────────────────────────────────────────────────────────────
def load_people():
    if os.path.exists(PEOPLE_FILE):
        with file_lock(PEOPLE_FILE):
            with open(PEOPLE_FILE) as f:
                return json.load(f)
    return []

def save_people(data):
    with file_lock(PEOPLE_FILE):
        with open(PEOPLE_FILE, "w") as f:
            json.dump(data, f, indent=2, default=str)


# ── Payroll ───────────────────────────────────────────────────────────────────
def load_payroll():
    if os.path.exists(PAYROLL_FILE):
        with file_lock(PAYROLL_FILE):
            with open(PAYROLL_FILE) as f:
                return json.load(f)
    return []

def save_payroll(data):
    with file_lock(PAYROLL_FILE):
        with open(PAYROLL_FILE, "w") as f:
            json.dump(data, f, indent=2, default=str)


# ── Job Costs ─────────────────────────────────────────────────────────────────
def load_jobcosts():
    if os.path.exists(JOBCOSTS_FILE):
        with file_lock(JOBCOSTS_FILE):
            with open(JOBCOSTS_FILE) as f:
                return json.load(f)
    return []

def save_jobcosts(data):
    with file_lock(JOBCOSTS_FILE):
        with open(JOBCOSTS_FILE, "w") as f:
            json.dump(data, f, indent=2)


# ── Followups ─────────────────────────────────────────────────────────────────
def load_followups():
    if os.path.exists(FOLLOWUPS_FILE):
        with file_lock(FOLLOWUPS_FILE):
            with open(FOLLOWUPS_FILE) as f:
                return json.load(f)
    return []

def load_nurtures():
    if os.path.exists(LEAD_NURTURES_FILE):
        with file_lock(LEAD_NURTURES_FILE):
            with open(LEAD_NURTURES_FILE) as f:
                return json.load(f)
    return []

def save_followups(data):
    with file_lock(FOLLOWUPS_FILE):
        with open(FOLLOWUPS_FILE, "w") as f:
            json.dump(data, f, indent=2, default=str)


# ── Leads (JSONL) ────────────────────────────────────────────────────────────
def load_leads():
    """Load all leads from the JSONL file with file locking."""
    leads = []
    if os.path.exists(LEADS_FILE):
        with file_lock(LEADS_FILE):
            with open(LEADS_FILE, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            leads.append(json.loads(line))
                        except Exception:
                            pass
    return leads

def append_lead(lead_data):
    """Append a lead to the JSON Lines file and log to Google Sheets."""
    with file_lock(LEADS_FILE):
        with open(LEADS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(lead_data, default=str) + "\n")
    if SHEETS_WEBHOOK:
        try:
            from utils.email import extract_email_phone
            email = lead_data.get("email", "")
            phone = lead_data.get("phone", "")
            if not email and not phone:
                email, phone = extract_email_phone(lead_data.get("contact", ""))
            sheets_data = {**lead_data, "email": email, "phone": phone, "score": lead_data.get("score", "")}
            requests.post(SHEETS_WEBHOOK, json=sheets_data, timeout=10)
        except Exception as e:
            print(f"Sheets logging failed: {e}")


# ── Lead Meta ─────────────────────────────────────────────────────────────────
def load_lead_meta():
    if os.path.exists(LEAD_META_FILE):
        with file_lock(LEAD_META_FILE):
            with open(LEAD_META_FILE) as f:
                return json.load(f)
    return {}

def save_lead_meta(data):
    with file_lock(LEAD_META_FILE):
        with open(LEAD_META_FILE, "w") as f:
            json.dump(data, f, indent=2, default=str)


# ── Lead Nurtures ─────────────────────────────────────────────────────────────
def load_lead_nurtures():
    if os.path.exists(LEAD_NURTURES_FILE):
        with file_lock(LEAD_NURTURES_FILE):
            with open(LEAD_NURTURES_FILE) as f:
                return json.load(f)
    return []

def save_lead_nurtures(data):
    with file_lock(LEAD_NURTURES_FILE):
        with open(LEAD_NURTURES_FILE, "w") as f:
            json.dump(data, f, indent=2, default=str)


# ── Lead Comms ────────────────────────────────────────────────────────────────
def load_lead_comms():
    if os.path.exists(LEAD_COMMS_FILE):
        with file_lock(LEAD_COMMS_FILE):
            with open(LEAD_COMMS_FILE) as f:
                return json.load(f)
    return []

def save_lead_comms(data):
    with file_lock(LEAD_COMMS_FILE):
        with open(LEAD_COMMS_FILE, "w") as f:
            json.dump(data, f, indent=2, default=str)


# ── Job Comms ─────────────────────────────────────────────────────────────────
def load_job_comms():
    if os.path.exists(JOB_COMMS_FILE):
        with file_lock(JOB_COMMS_FILE):
            with open(JOB_COMMS_FILE) as f:
                return json.load(f)
    return []

def save_job_comms(data):
    with file_lock(JOB_COMMS_FILE):
        with open(JOB_COMMS_FILE, "w") as f:
            json.dump(data, f, indent=2, default=str)


# ── Vendor Invoices ───────────────────────────────────────────────────────────
def load_vendor_invoices():
    if os.path.exists(VENDOR_INVOICES_FILE):
        with file_lock(VENDOR_INVOICES_FILE):
            with open(VENDOR_INVOICES_FILE) as f:
                return json.load(f)
    return []


# ── Invoice Inbox ─────────────────────────────────────────────────────────────
def load_invoice_inbox():
    if os.path.exists(INVOICE_INBOX_FILE):
        with file_lock(INVOICE_INBOX_FILE):
            with open(INVOICE_INBOX_FILE) as f:
                return json.load(f)
    return []

def save_invoice_inbox(data):
    with file_lock(INVOICE_INBOX_FILE):
        with open(INVOICE_INBOX_FILE, "w") as f:
            json.dump(data, f, indent=2)
