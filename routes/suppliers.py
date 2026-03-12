"""
Suppliers blueprint — supplier management, orders, transactions, notes.

Routes:
  /dashboard/api/suppliers                                      → GET / POST
  /dashboard/api/suppliers/<id>                                 → GET / PUT / DELETE
  /dashboard/api/suppliers/<id>/orders                          → GET / POST
  /dashboard/api/suppliers/<id>/orders/<oid>                    → PUT / DELETE
  /dashboard/api/suppliers/<id>/transactions                    → GET / POST
  /dashboard/api/suppliers/<id>/transactions/<tid>              → PUT / DELETE
  /dashboard/api/suppliers/<id>/notes                           → GET / POST
  /dashboard/api/suppliers/<id>/notes/<nid>                     → DELETE
"""

from flask import Blueprint, jsonify, request

from utils.auth import require_auth
from utils.suppliers_db import (
    create_note,
    create_order,
    create_supplier,
    create_transaction,
    delete_note,
    delete_order,
    delete_supplier,
    delete_transaction,
    get_notes,
    get_orders,
    get_supplier,
    get_transactions,
    load_suppliers,
    update_order,
    update_supplier,
    update_transaction,
)

suppliers_bp = Blueprint("suppliers", __name__)


# ── Suppliers ─────────────────────────────────────────────────────────────────

@suppliers_bp.route("/dashboard/api/suppliers")
def api_suppliers_list():
    return jsonify(load_suppliers())


@suppliers_bp.route("/dashboard/api/suppliers", methods=["POST"])
@require_auth
def api_suppliers_create():
    data = request.get_json() or {}
    if not data.get("name"):
        return jsonify({"error": "name is required"}), 400
    supplier = create_supplier(data)
    return jsonify(supplier), 201


@suppliers_bp.route("/dashboard/api/suppliers/<supplier_id>")
def api_supplier_get(supplier_id):
    supplier = get_supplier(supplier_id)
    if not supplier:
        return jsonify({"error": "Supplier not found"}), 404
    return jsonify(supplier)


@suppliers_bp.route("/dashboard/api/suppliers/<supplier_id>", methods=["PUT"])
@require_auth
def api_supplier_update(supplier_id):
    if not get_supplier(supplier_id):
        return jsonify({"error": "Supplier not found"}), 404
    data = request.get_json() or {}
    supplier = update_supplier(supplier_id, data)
    return jsonify(supplier)


@suppliers_bp.route("/dashboard/api/suppliers/<supplier_id>", methods=["DELETE"])
@require_auth
def api_supplier_delete(supplier_id):
    if not get_supplier(supplier_id):
        return jsonify({"error": "Supplier not found"}), 404
    delete_supplier(supplier_id)
    return jsonify({"ok": True})


# ── Orders ────────────────────────────────────────────────────────────────────

@suppliers_bp.route("/dashboard/api/suppliers/<supplier_id>/orders")
def api_orders_list(supplier_id):
    if not get_supplier(supplier_id):
        return jsonify({"error": "Supplier not found"}), 404
    return jsonify(get_orders(supplier_id))


@suppliers_bp.route("/dashboard/api/suppliers/<supplier_id>/orders", methods=["POST"])
@require_auth
def api_orders_create(supplier_id):
    if not get_supplier(supplier_id):
        return jsonify({"error": "Supplier not found"}), 404
    data = request.get_json() or {}
    order = create_order(supplier_id, data)
    return jsonify(order), 201


@suppliers_bp.route("/dashboard/api/suppliers/<supplier_id>/orders/<order_id>", methods=["PUT"])
@require_auth
def api_order_update(supplier_id, order_id):
    if not get_supplier(supplier_id):
        return jsonify({"error": "Supplier not found"}), 404
    data = request.get_json() or {}
    order = update_order(order_id, data)
    if not order:
        return jsonify({"error": "Order not found"}), 404
    return jsonify(order)


@suppliers_bp.route("/dashboard/api/suppliers/<supplier_id>/orders/<order_id>", methods=["DELETE"])
@require_auth
def api_order_delete(supplier_id, order_id):
    delete_order(order_id)
    return jsonify({"ok": True})


# ── Transactions ──────────────────────────────────────────────────────────────

@suppliers_bp.route("/dashboard/api/suppliers/<supplier_id>/transactions")
def api_transactions_list(supplier_id):
    if not get_supplier(supplier_id):
        return jsonify({"error": "Supplier not found"}), 404
    return jsonify(get_transactions(supplier_id))


@suppliers_bp.route("/dashboard/api/suppliers/<supplier_id>/transactions", methods=["POST"])
@require_auth
def api_transactions_create(supplier_id):
    if not get_supplier(supplier_id):
        return jsonify({"error": "Supplier not found"}), 404
    data = request.get_json() or {}
    txn = create_transaction(supplier_id, data)
    return jsonify(txn), 201


@suppliers_bp.route("/dashboard/api/suppliers/<supplier_id>/transactions/<transaction_id>", methods=["PUT"])
@require_auth
def api_transaction_update(supplier_id, transaction_id):
    if not get_supplier(supplier_id):
        return jsonify({"error": "Supplier not found"}), 404
    data = request.get_json() or {}
    txn = update_transaction(transaction_id, data)
    if not txn:
        return jsonify({"error": "Transaction not found"}), 404
    return jsonify(txn)


@suppliers_bp.route("/dashboard/api/suppliers/<supplier_id>/transactions/<transaction_id>", methods=["DELETE"])
@require_auth
def api_transaction_delete(supplier_id, transaction_id):
    delete_transaction(transaction_id)
    return jsonify({"ok": True})


# ── Notes ─────────────────────────────────────────────────────────────────────

@suppliers_bp.route("/dashboard/api/suppliers/<supplier_id>/notes")
def api_notes_list(supplier_id):
    if not get_supplier(supplier_id):
        return jsonify({"error": "Supplier not found"}), 404
    return jsonify(get_notes(supplier_id))


@suppliers_bp.route("/dashboard/api/suppliers/<supplier_id>/notes", methods=["POST"])
@require_auth
def api_notes_create(supplier_id):
    if not get_supplier(supplier_id):
        return jsonify({"error": "Supplier not found"}), 404
    data = request.get_json() or {}
    note = create_note(supplier_id, data)
    return jsonify(note), 201


@suppliers_bp.route("/dashboard/api/suppliers/<supplier_id>/notes/<note_id>", methods=["DELETE"])
@require_auth
def api_note_delete(supplier_id, note_id):
    delete_note(note_id)
    return jsonify({"ok": True})
