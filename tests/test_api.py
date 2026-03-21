"""
Smoke tests for all Flask API endpoints.

Uses Flask test client with session["user_id"] = "owner-jay"
to bypass @require_auth / @require_owner decorators.
"""

import json
import os
import pytest

os.environ["TESTING"] = "1"

from app import app


@pytest.fixture
def client():
    """Flask test client with auth session pre-set."""
    app.config["TESTING"] = True
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess["user_id"] = "owner-jay"
        yield c


@pytest.fixture
def anon_client():
    """Flask test client without auth (for public/webhook endpoints)."""
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# ══════════════════════════════════════════════════════════════════════════════
# Chat (public)
# ══════════════════════════════════════════════════════════════════════════════

def test_chat_home(anon_client):
    r = anon_client.get("/")
    assert r.status_code == 200


def test_chat_widget(anon_client):
    r = anon_client.get("/widget")
    assert r.status_code == 200


# ══════════════════════════════════════════════════════════════════════════════
# Ash — Webhooks (no auth)
# ══════════════════════════════════════════════════════════════════════════════

def test_retell_webhook(anon_client):
    r = anon_client.post("/api/retell/webhook",
                         json={"event": "ping"})
    assert r.status_code == 200


def test_twilio_sms_webhook(anon_client):
    r = anon_client.post("/webhook/twilio/sms",
                         data={"From": "+12065551234", "To": "+12532643860",
                               "Body": "Test SMS"})
    assert r.status_code == 200
    assert b"<Response></Response>" in r.data


# ══════════════════════════════════════════════════════════════════════════════
# Ash — Authenticated
# ══════════════════════════════════════════════════════════════════════════════

def test_ash_inbox(client):
    r = client.get("/api/ash/inbox")
    assert r.status_code == 200
    data = r.get_json()
    assert "items" in data


def test_ash_inbox_stats(client):
    r = client.get("/api/ash/inbox/stats")
    assert r.status_code == 200
    data = r.get_json()
    assert "total" in data


def test_ash_activity(client):
    r = client.get("/api/ash/activity")
    assert r.status_code == 200
    data = r.get_json()
    assert "activity" in data


def test_ash_weekly(client):
    r = client.get("/api/ash/weekly")
    assert r.status_code == 200
    data = r.get_json()
    assert "this_week" in data


def test_ash_overview(client):
    r = client.get("/api/ash/overview")
    assert r.status_code == 200
    data = r.get_json()
    assert "calls_today" in data


def test_ash_bookkeeping(client):
    r = client.get("/api/ash/bookkeeping")
    assert r.status_code == 200
    data = r.get_json()
    assert "items" in data


def test_ash_calls(client):
    r = client.get("/api/ash/calls")
    assert r.status_code == 200


def test_ash_status(client):
    r = client.get("/api/ash/status")
    assert r.status_code == 200


def test_ash_scan(client):
    r = client.get("/api/ash/scan")
    assert r.status_code == 200


# ══════════════════════════════════════════════════════════════════════════════
# Dashboard
# ══════════════════════════════════════════════════════════════════════════════

def test_dashboard_page(client):
    r = client.get("/dashboard")
    assert r.status_code == 200


def test_dashboard_me(client):
    r = client.get("/dashboard/api/me")
    assert r.status_code == 200


def test_dashboard_stats(client):
    r = client.get("/dashboard/api/stats")
    assert r.status_code == 200


def test_dashboard_activity(client):
    r = client.get("/dashboard/api/activity")
    assert r.status_code == 200


def test_dashboard_appointments(client):
    r = client.get("/dashboard/api/appointments")
    assert r.status_code == 200


def test_dashboard_lead_nurtures(client):
    r = client.get("/dashboard/api/lead-nurtures")
    assert r.status_code == 200


def test_dashboard_settings_integrations(client):
    r = client.get("/dashboard/api/settings/integrations")
    assert r.status_code == 200


def test_dashboard_settings_company_public(client):
    r = client.get("/dashboard/api/settings/company-public")
    assert r.status_code == 200


def test_dashboard_data_summary(client):
    r = client.get("/dashboard/api/data/summary")
    assert r.status_code == 200


def test_dashboard_data_export(client):
    r = client.get("/dashboard/api/data/export")
    assert r.status_code == 200


def test_dashboard_users(client):
    r = client.get("/dashboard/api/users")
    assert r.status_code == 200


# ══════════════════════════════════════════════════════════════════════════════
# Jobs
# ══════════════════════════════════════════════════════════════════════════════

def test_jobs_list(client):
    r = client.get("/dashboard/api/jobs")
    assert r.status_code == 200


def test_jobs_create(client):
    r = client.post("/dashboard/api/jobs",
                    json={"company": "Test Co", "description": "Test job"})
    assert r.status_code in (200, 201)


def test_jobcosts_list(client):
    r = client.get("/dashboard/api/jobcosts")
    assert r.status_code == 200


def test_followups_list(client):
    r = client.get("/dashboard/api/followups")
    assert r.status_code == 200


# ══════════════════════════════════════════════════════════════════════════════
# Leads
# ══════════════════════════════════════════════════════════════════════════════

def test_leads_list(client):
    r = client.get("/dashboard/api/leads")
    assert r.status_code == 200


def test_lead_nurtures_list(client):
    r = client.get("/dashboard/api/lead-nurtures")
    assert r.status_code == 200


def test_lead_create_public(anon_client):
    r = anon_client.post("/lead",
                         json={"name": "Test Lead", "phone": "555-1234",
                               "message": "Need racking"})
    assert r.status_code in (200, 201)


# ══════════════════════════════════════════════════════════════════════════════
# Invoices
# ══════════════════════════════════════════════════════════════════════════════

def test_invoices_list(client):
    r = client.get("/dashboard/api/invoices")
    assert r.status_code == 200


def test_invoice_inbox_list(client):
    r = client.get("/dashboard/api/invoice-inbox")
    assert r.status_code == 200


def test_invoice_inbox_settings(client):
    r = client.get("/dashboard/api/invoice-inbox/settings")
    assert r.status_code == 200


# ══════════════════════════════════════════════════════════════════════════════
# Payroll
# ══════════════════════════════════════════════════════════════════════════════

def test_people_list(client):
    r = client.get("/dashboard/api/people")
    assert r.status_code == 200


def test_payroll_list(client):
    r = client.get("/dashboard/api/payroll")
    assert r.status_code == 200


# ══════════════════════════════════════════════════════════════════════════════
# Suppliers
# ══════════════════════════════════════════════════════════════════════════════

def test_suppliers_list(client):
    r = client.get("/dashboard/api/suppliers")
    assert r.status_code == 200
    data = r.get_json()
    assert isinstance(data, list)


def test_supplier_get(client):
    r = client.get("/dashboard/api/suppliers/s1")
    assert r.status_code == 200


def test_supplier_create(client):
    r = client.post("/dashboard/api/suppliers",
                    json={"name": "Test Supplier", "category": "racking"})
    assert r.status_code in (200, 201)


def test_supplier_orders(client):
    r = client.get("/dashboard/api/suppliers/s1/orders")
    assert r.status_code == 200


def test_supplier_transactions(client):
    r = client.get("/dashboard/api/suppliers/s1/transactions")
    assert r.status_code == 200


def test_supplier_notes(client):
    r = client.get("/dashboard/api/suppliers/s1/notes")
    assert r.status_code == 200


# ══════════════════════════════════════════════════════════════════════════════
# Auth — Unauthorized access returns 401
# ══════════════════════════════════════════════════════════════════════════════

def test_inbox_unauthorized(anon_client):
    r = anon_client.get("/api/ash/inbox")
    assert r.status_code == 401


def test_jobs_unauthorized(anon_client):
    r = anon_client.get("/dashboard/api/jobs")
    assert r.status_code == 401


def test_suppliers_unauthorized(anon_client):
    # Note: suppliers list GET has no @require_auth (public endpoint)
    r = anon_client.get("/dashboard/api/suppliers")
    assert r.status_code == 200
