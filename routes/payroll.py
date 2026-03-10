"""
Payroll blueprint — people (staff & subs) CRUD, payroll records, paystub viewer.

Routes:
  /dashboard/api/people                              → GET / POST
  /dashboard/api/people/<id>                         → PUT / DELETE
  /dashboard/api/people/<id>/recalculate-pending     → POST
  /dashboard/api/payroll                             → GET / POST
  /dashboard/api/payroll/<id>                        → PUT / DELETE
  /dashboard/paystub/<id>                            → GET (rendered HTML)
"""

import uuid
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

from utils.auth import require_auth
from utils.data import load_payroll, load_people, save_payroll, save_people
from utils.html_generators import _paystub_html

payroll_bp = Blueprint("payroll", __name__)


# ── People (staff & subcontractors) ──────────────────────────────────────────

@payroll_bp.route("/dashboard/api/people", methods=["GET"])
@require_auth
def get_people():
    people = load_people()
    people.sort(key=lambda x: (x.get("type", ""), x.get("name", "").lower()))
    return jsonify(people)


@payroll_bp.route("/dashboard/api/people", methods=["POST"])
@require_auth
def create_person():
    data = request.json or {}
    people = load_people()
    person = {
        "person_id": str(uuid.uuid4()),
        "name": data.get("name", "").strip(),
        "type": data.get("type", "employee"),
        "role": data.get("role", "").strip(),
        "company": data.get("company", "").strip(),
        "phone": data.get("phone", "").strip(),
        "email": data.get("email", "").strip(),
        "notes": data.get("notes", "").strip(),
        "pay_type": data.get("pay_type", ""),
        "pay_rate": float(data.get("pay_rate") or 0),
        "pay_terms": data.get("pay_terms", ""),
        "qb_type": data.get("qb_type", ""),
        "tax_id": data.get("tax_id", "").strip(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    people.append(person)
    save_people(people)
    return jsonify(person), 201


@payroll_bp.route("/dashboard/api/people/<person_id>", methods=["PUT"])
@require_auth
def update_person(person_id):
    data = request.json or {}
    people = load_people()
    for p in people:
        if p["person_id"] == person_id:
            comp_fields = {"pay_type", "pay_rate", "pay_terms", "qb_type", "tax_id"}
            comp_changed = any(
                k in data and data[k] != p.get(k) for k in comp_fields
            )
            for k in ("name", "type", "role", "company", "phone", "email",
                       "notes", "pay_type", "pay_terms", "qb_type", "tax_id",
                       "department"):
                if k in data:
                    p[k] = str(data[k]).strip()
            for k in ("pay_rate",):
                if k in data:
                    p[k] = float(data[k] or 0)
            if comp_changed:
                p["comp_last_modified"] = datetime.now().strftime("%Y-%m-%d")
            save_people(people)
            return jsonify(p)
    return jsonify({"error": "Not found"}), 404


@payroll_bp.route("/dashboard/api/people/<person_id>", methods=["DELETE"])
@require_auth
def delete_person(person_id):
    people = load_people()
    people = [p for p in people if p["person_id"] != person_id]
    save_people(people)
    return jsonify({"ok": True})


# ── Payroll records ───────────────────────────────────────────────────────────

@payroll_bp.route("/dashboard/api/payroll", methods=["GET"])
@require_auth
def get_payroll():
    person_id = request.args.get("person_id")
    records = load_payroll()
    if person_id:
        records = [r for r in records if r.get("person_id") == person_id]
    records.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return jsonify(records)


@payroll_bp.route("/dashboard/api/payroll", methods=["POST"])
@require_auth
def create_pay_record():
    data = request.json or {}
    records = load_payroll()
    record = {
        "pay_id": str(uuid.uuid4()),
        "person_id": data.get("person_id", ""),
        "job_id": data.get("job_id", ""),
        "job_number": data.get("job_number", ""),
        "description": data.get("description", "").strip(),
        "amount_due": float(data.get("amount_due") or 0),
        "amount_paid": float(data.get("amount_paid") or 0),
        "status": data.get("status", "pending"),
        "pay_date": data.get("pay_date", ""),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    records.append(record)
    save_payroll(records)
    return jsonify(record), 201


@payroll_bp.route("/dashboard/api/payroll/<pay_id>", methods=["PUT"])
@require_auth
def update_pay_record(pay_id):
    data = request.json or {}
    records = load_payroll()
    for r in records:
        if r["pay_id"] == pay_id:
            for k in ("description", "job_id", "job_number", "status", "pay_date"):
                if k in data:
                    r[k] = str(data[k]).strip()
            for k in ("amount_due", "amount_paid"):
                if k in data:
                    r[k] = float(data[k] or 0)
            save_payroll(records)
            return jsonify(r)
    return jsonify({"error": "Not found"}), 404


@payroll_bp.route("/dashboard/api/payroll/<pay_id>", methods=["DELETE"])
@require_auth
def delete_pay_record(pay_id):
    records = load_payroll()
    records = [r for r in records if r["pay_id"] != pay_id]
    save_payroll(records)
    return jsonify({"ok": True})


# ── Recalculate pending pay records after a rate change ───────────────────────

@payroll_bp.route("/dashboard/api/people/<person_id>/recalculate-pending", methods=["POST"])
@require_auth
def recalculate_pending(person_id):
    """Recalculate amount_due on all pending pay records after a rate change."""
    data = request.json or {}
    pay_type = data.get("pay_type", "salary")
    pay_rate = float(data.get("pay_rate", 0))
    pay_terms = data.get("pay_terms", "biweekly")

    if pay_type == "salary":
        divisor = 52 if pay_terms == "weekly" else 26
        new_amount = round(pay_rate / divisor, 2)
    elif pay_type == "hourly":
        hours = 40 if pay_terms == "weekly" else 80
        new_amount = round(pay_rate * hours, 2)
    else:
        return jsonify({"ok": True, "updated": 0, "new_amount": 0})

    records = load_payroll()
    updated = 0
    for r in records:
        if r.get("person_id") == person_id and r.get("status") in ("pending", ""):
            r["amount_due"] = new_amount
            r["amount_paid"] = 0.0
            updated += 1
    save_payroll(records)
    return jsonify({"ok": True, "updated": updated, "new_amount": new_amount})


# ── Pay stub viewer ───────────────────────────────────────────────────────────

@payroll_bp.route("/dashboard/paystub/<pay_id>")
def view_paystub(pay_id):
    records = load_payroll()
    record = next((r for r in records if r["pay_id"] == pay_id), None)
    if not record:
        return (
            "<h3 style='font-family:sans-serif;padding:40px;color:#888'>"
            "Pay record not found.</h3>"
        ), 404
    people = load_people()
    person = next(
        (p for p in people if p["person_id"] == record["person_id"]), {},
    )

    pay_date = record.get("pay_date", "")
    ytd_year = pay_date[:4]
    ytd_recs = [
        r for r in records
        if r["person_id"] == record["person_id"]
        and r.get("status") == "paid"
        and r.get("pay_date", "")[:4] == ytd_year
        and r.get("pay_date", "") <= pay_date
    ]
    ytd_gross = sum(r.get("amount_due", 0) for r in ytd_recs)
    ytd_paid = sum(r.get("amount_paid", 0) for r in ytd_recs)

    return _paystub_html(record, person, ytd_gross, ytd_paid)
