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
  /api/orders/<order_id>/communications                         → GET / POST
  /api/orders/<order_id>/documents                              → GET / POST / DELETE
  /api/documents/<doc_id>/download                              → GET
"""

from flask import Blueprint, Response, jsonify, request, send_file

from utils.auth import require_auth
from utils.suppliers_db import (
    create_note,
    create_order,
    create_order_communication,
    create_order_document,
    create_order_line_item,
    create_supplier,
    create_timeline_event,
    create_transaction,
    delete_note,
    delete_order,
    delete_order_document,
    delete_order_line_item,
    delete_supplier,
    delete_transaction,
    get_notes,
    get_order_communications,
    get_order_document_file,
    get_order_documents,
    get_order_line_items,
    get_order_timeline,
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


# ── Order Communications ─────────────────────────────────────────────────────

@suppliers_bp.route("/api/orders/<order_id>/communications")
def api_order_comms_list(order_id):
    return jsonify(get_order_communications(order_id))


@suppliers_bp.route("/api/orders/<order_id>/communications", methods=["POST"])
@require_auth
def api_order_comms_create(order_id):
    data = request.get_json() or {}
    if not data.get("note", "").strip():
        return jsonify({"error": "note is required"}), 400
    comm = create_order_communication(order_id, {"note": data["note"].strip(), "author": "Jay"})
    return jsonify(comm), 201


# ── Order Documents ──────────────────────────────────────────────────────────

@suppliers_bp.route("/api/orders/<order_id>/documents")
def api_order_docs_list(order_id):
    return jsonify(get_order_documents(order_id))


@suppliers_bp.route("/api/orders/<order_id>/documents", methods=["POST"])
@require_auth
def api_order_docs_upload(order_id):
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"error": "file is required"}), 400
    doc_type = request.form.get("doc_type", "other")
    file_bytes = f.read()
    size = len(file_bytes)
    if size < 1024:
        size_str = f"{size} B"
    elif size < 1024 * 1024:
        size_str = f"{size / 1024:.1f} KB"
    else:
        size_str = f"{size / (1024 * 1024):.1f} MB"
    doc = create_order_document(order_id, {
        "doc_type": doc_type,
        "filename": f.filename,
        "file_size": size_str,
        "file_data": file_bytes,
    })
    return jsonify(doc), 201


@suppliers_bp.route("/api/orders/<order_id>/documents/<doc_id>", methods=["DELETE"])
@require_auth
def api_order_doc_delete(order_id, doc_id):
    delete_order_document(doc_id)
    return jsonify({"ok": True})


# ── Order Line Items ──────────────────────────────────────────────────────────

@suppliers_bp.route("/api/orders/<order_id>/line-items")
def api_order_line_items_list(order_id):
    return jsonify(get_order_line_items(order_id))


@suppliers_bp.route("/api/orders/<order_id>/line-items", methods=["POST"])
@require_auth
def api_order_line_items_create(order_id):
    data = request.get_json() or {}
    if not data.get("description", "").strip():
        return jsonify({"error": "description is required"}), 400
    item = create_order_line_item(order_id, {
        "description": data["description"].strip(),
        "quantity": data.get("quantity", 1),
        "unit_price": data.get("unit_price", 0),
    })
    create_timeline_event(order_id, {
        "event_type": "note_added",
        "label": "Line item added",
        "detail": item["description"][:60],
        "actor": "Jay",
    })
    return jsonify(item), 201


@suppliers_bp.route("/api/orders/<order_id>/line-items/<item_id>", methods=["DELETE"])
@require_auth
def api_order_line_item_delete(order_id, item_id):
    delete_order_line_item(item_id)
    return jsonify({"ok": True})


# ── Order Timeline ────────────────────────────────────────────────────────────

@suppliers_bp.route("/api/orders/<order_id>/timeline")
def api_order_timeline_list(order_id):
    return jsonify(get_order_timeline(order_id))


@suppliers_bp.route("/api/documents/<doc_id>/meta")
def api_doc_meta(doc_id):
    docs = None
    with __import__('sqlite3').connect(__import__('utils.suppliers_db', fromlist=['DB_PATH']).DB_PATH) as conn:
        conn.row_factory = __import__('sqlite3').Row
        row = conn.execute(
            "SELECT id, order_id, doc_type, filename, file_size, uploaded_at FROM order_documents WHERE id = ?",
            (doc_id,),
        ).fetchone()
    if not row:
        return jsonify({"error": "Document not found"}), 404
    doc = dict(row)
    # Enrich with order + supplier info
    from utils.suppliers_db import DB_PATH as _dbp
    import sqlite3 as _sql
    c2 = _sql.connect(_dbp)
    c2.row_factory = _sql.Row
    order = c2.execute(
        "SELECT description, order_date, status, supplier_id FROM supplier_orders WHERE id = ?",
        (doc["order_id"],),
    ).fetchone()
    if order:
        order = dict(order)
        doc["item_description"] = order.get("description", "")
        doc["order_date"] = order.get("order_date", "")
        doc["status"] = order.get("status", "")
        supplier = c2.execute(
            "SELECT name FROM suppliers WHERE id = ?", (order.get("supplier_id", ""),)
        ).fetchone()
        doc["supplier_name"] = supplier["name"] if supplier else ""
    c2.close()
    return jsonify(doc)


@suppliers_bp.route("/api/documents/<doc_id>/download")
def api_doc_download(doc_id):
    row = get_order_document_file(doc_id)
    if not row:
        return jsonify({"error": "Document not found"}), 404
    import io
    import mimetypes
    mime = mimetypes.guess_type(row["filename"])[0] or "application/octet-stream"
    return send_file(
        io.BytesIO(row["file_data"] or b""),
        mimetype=mime,
        as_attachment=False,
        download_name=row["filename"],
    )
