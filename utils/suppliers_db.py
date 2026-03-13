"""
SQLite database layer for supplier management.

Tables: suppliers, supplier_transactions, supplier_notes
DB path: utils/data/suppliers.db (overridable via SUPPLIERS_DB env var)
"""

import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

DB_PATH = os.environ.get(
    "SUPPLIERS_DB",
    os.path.join(os.path.dirname(__file__), "data", "suppliers.db"),
)


@contextmanager
def _get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Schema ────────────────────────────────────────────────────────────────────

def init_db():
    """Create tables if they don't exist."""
    with _get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS suppliers (
                id              TEXT PRIMARY KEY,
                name            TEXT NOT NULL,
                category        TEXT NOT NULL DEFAULT '',
                phone           TEXT NOT NULL DEFAULT '',
                website         TEXT NOT NULL DEFAULT '',
                rep             TEXT NOT NULL DEFAULT '',
                status          TEXT NOT NULL DEFAULT 'active',
                notes           TEXT NOT NULL DEFAULT '',
                qb_vendor_id    TEXT,
                qb_sync_token   TEXT,
                qb_last_synced  TEXT,
                created_at      TEXT NOT NULL,
                updated_at      TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS supplier_transactions (
                id                TEXT PRIMARY KEY,
                supplier_id       TEXT NOT NULL REFERENCES suppliers(id) ON DELETE CASCADE,
                job_id            TEXT,
                type              TEXT NOT NULL DEFAULT '',
                status            TEXT NOT NULL DEFAULT 'pending',
                amount            REAL NOT NULL DEFAULT 0,
                currency          TEXT NOT NULL DEFAULT 'USD',
                description       TEXT NOT NULL DEFAULT '',
                ref_number        TEXT NOT NULL DEFAULT '',
                transaction_date  TEXT,
                due_date          TEXT,
                paid_date         TEXT,
                source            TEXT NOT NULL DEFAULT 'manual',
                qb_transaction_id TEXT,
                qb_bill_id        TEXT,
                qb_payment_id     TEXT,
                created_at        TEXT NOT NULL,
                updated_at        TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS supplier_orders (
                id                 TEXT PRIMARY KEY,
                supplier_id        TEXT NOT NULL REFERENCES suppliers(id) ON DELETE CASCADE,
                job_id             TEXT,
                description        TEXT NOT NULL DEFAULT '',
                quantity           REAL NOT NULL DEFAULT 0,
                unit               TEXT NOT NULL DEFAULT '',
                unit_price         REAL NOT NULL DEFAULT 0,
                total_amount       REAL NOT NULL DEFAULT 0,
                order_date         TEXT,
                expected_delivery  TEXT,
                delivered_date     TEXT,
                status             TEXT NOT NULL DEFAULT 'pending',
                notes              TEXT NOT NULL DEFAULT '',
                created_at         TEXT NOT NULL,
                updated_at         TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS supplier_notes (
                id          TEXT PRIMARY KEY,
                supplier_id TEXT NOT NULL REFERENCES suppliers(id) ON DELETE CASCADE,
                body        TEXT NOT NULL DEFAULT '',
                author      TEXT NOT NULL DEFAULT '',
                created_at  TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS order_communications (
                id          TEXT PRIMARY KEY,
                order_id    TEXT NOT NULL,
                author      TEXT NOT NULL DEFAULT '',
                note        TEXT NOT NULL DEFAULT '',
                created_at  TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS order_timeline (
                id          TEXT PRIMARY KEY,
                order_id    TEXT NOT NULL,
                event_type  TEXT NOT NULL,
                label       TEXT NOT NULL,
                detail      TEXT,
                actor       TEXT,
                created_at  TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS order_line_items (
                id          TEXT PRIMARY KEY,
                order_id    TEXT NOT NULL,
                description TEXT NOT NULL,
                quantity    REAL NOT NULL DEFAULT 1,
                unit_price  REAL NOT NULL DEFAULT 0,
                created_at  TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS order_documents (
                id          TEXT PRIMARY KEY,
                order_id    TEXT NOT NULL,
                doc_type    TEXT NOT NULL,
                filename    TEXT NOT NULL,
                file_size   TEXT,
                uploaded_at TEXT NOT NULL,
                file_data   BLOB
            );
        """)


# ── Suppliers CRUD ────────────────────────────────────────────────────────────

def load_suppliers():
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM suppliers ORDER BY name"
        ).fetchall()
    return [dict(r) for r in rows]


def get_supplier(supplier_id):
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM suppliers WHERE id = ?", (supplier_id,)
        ).fetchone()
    return dict(row) if row else None


def create_supplier(data):
    now = datetime.now(timezone.utc).isoformat()
    supplier = {
        "id": data.get("id") or str(uuid.uuid4()),
        "name": data.get("name", ""),
        "category": data.get("category", ""),
        "phone": data.get("phone", ""),
        "website": data.get("website", ""),
        "rep": data.get("rep", ""),
        "status": data.get("status", "active"),
        "notes": data.get("notes", ""),
        "qb_vendor_id": data.get("qb_vendor_id"),
        "qb_sync_token": data.get("qb_sync_token"),
        "qb_last_synced": data.get("qb_last_synced"),
        "created_at": now,
        "updated_at": now,
    }
    with _get_conn() as conn:
        conn.execute(
            """INSERT INTO suppliers
               (id, name, category, phone, website, rep, status, notes,
                qb_vendor_id, qb_sync_token, qb_last_synced, created_at, updated_at)
               VALUES (:id, :name, :category, :phone, :website, :rep, :status, :notes,
                       :qb_vendor_id, :qb_sync_token, :qb_last_synced, :created_at, :updated_at)""",
            supplier,
        )
    return supplier


def update_supplier(supplier_id, data):
    now = datetime.now(timezone.utc).isoformat()
    fields = [
        "name", "category", "phone", "website", "rep", "status", "notes",
        "qb_vendor_id", "qb_sync_token", "qb_last_synced",
    ]
    sets = []
    params = {}
    for f in fields:
        if f in data:
            sets.append(f"{f} = :{f}")
            params[f] = data[f]
    if not sets:
        return get_supplier(supplier_id)
    sets.append("updated_at = :updated_at")
    params["updated_at"] = now
    params["id"] = supplier_id
    with _get_conn() as conn:
        conn.execute(
            f"UPDATE suppliers SET {', '.join(sets)} WHERE id = :id", params
        )
    return get_supplier(supplier_id)


def delete_supplier(supplier_id):
    with _get_conn() as conn:
        conn.execute("DELETE FROM suppliers WHERE id = ?", (supplier_id,))


# ── Transactions CRUD ─────────────────────────────────────────────────────────

def get_transactions(supplier_id):
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM supplier_transactions WHERE supplier_id = ? ORDER BY transaction_date DESC",
            (supplier_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def create_transaction(supplier_id, data):
    now = datetime.now(timezone.utc).isoformat()
    txn = {
        "id": str(uuid.uuid4()),
        "supplier_id": supplier_id,
        "job_id": data.get("job_id"),
        "type": data.get("type", ""),
        "status": data.get("status", "pending"),
        "amount": data.get("amount", 0),
        "currency": data.get("currency", "USD"),
        "description": data.get("description", ""),
        "ref_number": data.get("ref_number", ""),
        "transaction_date": data.get("transaction_date"),
        "due_date": data.get("due_date"),
        "paid_date": data.get("paid_date"),
        "source": data.get("source", "manual"),
        "qb_transaction_id": data.get("qb_transaction_id"),
        "qb_bill_id": data.get("qb_bill_id"),
        "qb_payment_id": data.get("qb_payment_id"),
        "created_at": now,
        "updated_at": now,
    }
    with _get_conn() as conn:
        conn.execute(
            """INSERT INTO supplier_transactions
               (id, supplier_id, job_id, type, status, amount, currency,
                description, ref_number, transaction_date, due_date, paid_date,
                source, qb_transaction_id, qb_bill_id, qb_payment_id,
                created_at, updated_at)
               VALUES (:id, :supplier_id, :job_id, :type, :status, :amount, :currency,
                       :description, :ref_number, :transaction_date, :due_date, :paid_date,
                       :source, :qb_transaction_id, :qb_bill_id, :qb_payment_id,
                       :created_at, :updated_at)""",
            txn,
        )
    return txn


def update_transaction(transaction_id, data):
    now = datetime.now(timezone.utc).isoformat()
    fields = [
        "job_id", "type", "status", "amount", "currency", "description",
        "ref_number", "transaction_date", "due_date", "paid_date",
        "source", "qb_transaction_id", "qb_bill_id", "qb_payment_id",
    ]
    sets = []
    params = {}
    for f in fields:
        if f in data:
            sets.append(f"{f} = :{f}")
            params[f] = data[f]
    if not sets:
        return None
    sets.append("updated_at = :updated_at")
    params["updated_at"] = now
    params["id"] = transaction_id
    with _get_conn() as conn:
        conn.execute(
            f"UPDATE supplier_transactions SET {', '.join(sets)} WHERE id = :id",
            params,
        )
        row = conn.execute(
            "SELECT * FROM supplier_transactions WHERE id = ?", (transaction_id,)
        ).fetchone()
    return dict(row) if row else None


def delete_transaction(transaction_id):
    with _get_conn() as conn:
        conn.execute(
            "DELETE FROM supplier_transactions WHERE id = ?", (transaction_id,)
        )


# ── Orders CRUD ────────────────────────────────────────────────────────────────

def get_orders(supplier_id):
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM supplier_orders WHERE supplier_id = ? ORDER BY order_date DESC",
            (supplier_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def create_order(supplier_id, data):
    now = datetime.now(timezone.utc).isoformat()
    qty = data.get("quantity", 0) or 0
    price = data.get("unit_price", 0) or 0
    order = {
        "id": str(uuid.uuid4()),
        "supplier_id": supplier_id,
        "job_id": data.get("job_id"),
        "description": data.get("description", ""),
        "quantity": qty,
        "unit": data.get("unit", ""),
        "unit_price": price,
        "total_amount": data.get("total_amount") if data.get("total_amount") is not None else qty * price,
        "order_date": data.get("order_date"),
        "expected_delivery": data.get("expected_delivery"),
        "delivered_date": data.get("delivered_date"),
        "status": data.get("status", "pending"),
        "notes": data.get("notes", ""),
        "created_at": now,
        "updated_at": now,
    }
    with _get_conn() as conn:
        conn.execute(
            """INSERT INTO supplier_orders
               (id, supplier_id, job_id, description, quantity, unit, unit_price,
                total_amount, order_date, expected_delivery, delivered_date,
                status, notes, created_at, updated_at)
               VALUES (:id, :supplier_id, :job_id, :description, :quantity, :unit, :unit_price,
                       :total_amount, :order_date, :expected_delivery, :delivered_date,
                       :status, :notes, :created_at, :updated_at)""",
            order,
        )
    return order


def update_order(order_id, data):
    now = datetime.now(timezone.utc).isoformat()
    fields = [
        "job_id", "description", "quantity", "unit", "unit_price",
        "total_amount", "order_date", "expected_delivery", "delivered_date",
        "status", "notes",
    ]
    sets = []
    params = {}
    for f in fields:
        if f in data:
            sets.append(f"{f} = :{f}")
            params[f] = data[f]
    if not sets:
        return None
    sets.append("updated_at = :updated_at")
    params["updated_at"] = now
    params["id"] = order_id
    with _get_conn() as conn:
        conn.execute(
            f"UPDATE supplier_orders SET {', '.join(sets)} WHERE id = :id",
            params,
        )
        row = conn.execute(
            "SELECT * FROM supplier_orders WHERE id = ?", (order_id,)
        ).fetchone()
    return dict(row) if row else None


def delete_order(order_id):
    with _get_conn() as conn:
        conn.execute("DELETE FROM supplier_orders WHERE id = ?", (order_id,))


# ── Notes CRUD ────────────────────────────────────────────────────────────────

def get_notes(supplier_id):
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM supplier_notes WHERE supplier_id = ? ORDER BY created_at DESC",
            (supplier_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def create_note(supplier_id, data):
    now = datetime.now(timezone.utc).isoformat()
    note = {
        "id": str(uuid.uuid4()),
        "supplier_id": supplier_id,
        "body": data.get("body", ""),
        "author": data.get("author", ""),
        "created_at": now,
    }
    with _get_conn() as conn:
        conn.execute(
            """INSERT INTO supplier_notes (id, supplier_id, body, author, created_at)
               VALUES (:id, :supplier_id, :body, :author, :created_at)""",
            note,
        )
    return note


def delete_note(note_id):
    with _get_conn() as conn:
        conn.execute("DELETE FROM supplier_notes WHERE id = ?", (note_id,))


# ── Order Communications CRUD ─────────────────────────────────────────────────

def get_order_communications(order_id):
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM order_communications WHERE order_id = ? ORDER BY created_at DESC",
            (order_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def create_order_communication(order_id, data):
    now = datetime.now(timezone.utc).isoformat()
    comm = {
        "id": str(uuid.uuid4()),
        "order_id": order_id,
        "author": data.get("author", "Jay"),
        "note": data.get("note", ""),
        "created_at": now,
    }
    with _get_conn() as conn:
        conn.execute(
            """INSERT INTO order_communications (id, order_id, author, note, created_at)
               VALUES (:id, :order_id, :author, :note, :created_at)""",
            comm,
        )
    return comm


# ── Order Line Items CRUD ─────────────────────────────────────────────────────

def get_order_line_items(order_id):
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM order_line_items WHERE order_id = ? ORDER BY created_at ASC",
            (order_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def create_order_line_item(order_id, data):
    now = datetime.now(timezone.utc).isoformat()
    item = {
        "id": str(uuid.uuid4()),
        "order_id": order_id,
        "description": data.get("description", ""),
        "quantity": data.get("quantity", 1),
        "unit_price": data.get("unit_price", 0),
        "created_at": data.get("created_at", now),
    }
    with _get_conn() as conn:
        conn.execute(
            """INSERT INTO order_line_items (id, order_id, description, quantity, unit_price, created_at)
               VALUES (:id, :order_id, :description, :quantity, :unit_price, :created_at)""",
            item,
        )
    return item


def delete_order_line_item(item_id):
    with _get_conn() as conn:
        conn.execute("DELETE FROM order_line_items WHERE id = ?", (item_id,))


# ── Order Timeline CRUD ───────────────────────────────────────────────────────

def get_order_timeline(order_id):
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM order_timeline WHERE order_id = ? ORDER BY created_at DESC",
            (order_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def create_timeline_event(order_id, data):
    now = datetime.now(timezone.utc).isoformat()
    event = {
        "id": str(uuid.uuid4()),
        "order_id": order_id,
        "event_type": data.get("event_type", ""),
        "label": data.get("label", ""),
        "detail": data.get("detail"),
        "actor": data.get("actor", "System"),
        "created_at": data.get("created_at", now),
    }
    with _get_conn() as conn:
        conn.execute(
            """INSERT INTO order_timeline (id, order_id, event_type, label, detail, actor, created_at)
               VALUES (:id, :order_id, :event_type, :label, :detail, :actor, :created_at)""",
            event,
        )
    return event


# ── Order Documents CRUD ──────────────────────────────────────────────────────

def get_order_documents(order_id):
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT id, order_id, doc_type, filename, file_size, uploaded_at FROM order_documents WHERE order_id = ? ORDER BY uploaded_at DESC",
            (order_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def create_order_document(order_id, data):
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": str(uuid.uuid4()),
        "order_id": order_id,
        "doc_type": data.get("doc_type", "other"),
        "filename": data.get("filename", ""),
        "file_size": data.get("file_size", ""),
        "uploaded_at": data.get("uploaded_at", now),
        "file_data": data.get("file_data", b""),
    }
    with _get_conn() as conn:
        conn.execute(
            """INSERT INTO order_documents (id, order_id, doc_type, filename, file_size, uploaded_at, file_data)
               VALUES (:id, :order_id, :doc_type, :filename, :file_size, :uploaded_at, :file_data)""",
            doc,
        )
    return {k: v for k, v in doc.items() if k != "file_data"}


def get_order_document_file(doc_id):
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT filename, file_data FROM order_documents WHERE id = ?", (doc_id,)
        ).fetchone()
    return dict(row) if row else None


def delete_order_document(doc_id):
    with _get_conn() as conn:
        conn.execute("DELETE FROM order_documents WHERE id = ?", (doc_id,))


# ── Seed data ─────────────────────────────────────────────────────────────────

_SEED_SUPPLIERS = [
    {"id": "s1",  "name": "UNARCO Material Handling",     "category": "racking",   "phone": "800-868-5238", "website": "unarcorack.com",        "status": "active",    "notes": "Leading pallet rack manufacturer. Structural & roll-formed systems."},
    {"id": "s2",  "name": "Interlake Mecalux",            "category": "racking",   "phone": "877-632-2589", "website": "interlakemecalux.com",   "status": "active",    "notes": "Global racking solutions. Quick Ship program available."},
    {"id": "s3",  "name": "Speedrack West",               "category": "racking",   "phone": "800-736-6551", "website": "speedrackwest.com",      "status": "active",    "notes": "Ships from 15+ US warehouses. CAD design & permit services."},
    {"id": "s4",  "name": "Advance Storage Products",     "category": "racking",   "phone": "800-869-1701", "website": "advancestorage.com",     "status": "active",    "notes": "Gold standard pushback systems. 50% US market share."},
    {"id": "s5",  "name": "Ridg-U-Rack",                  "category": "racking",   "phone": "814-781-1234", "website": "ridgurack.com",          "status": "active",    "notes": "High-density pallet rack systems. Drive-in & push-back specialists."},
    {"id": "s6",  "name": "Wildeck",                      "category": "mezzanine", "phone": "800-325-6939", "website": "wildeck.com",            "status": "preferred", "notes": "Top mezzanine brand. Used extensively in WA/PNW region."},
    {"id": "s7",  "name": "Panel Built",                  "category": "mezzanine", "phone": "800-636-3873", "website": "panelbuilt.com",         "status": "active",    "notes": "Mezzanines & modular offices since 1995. Custom builds available."},
    {"id": "s8",  "name": "Cogan",                        "category": "mezzanine", "phone": "800-263-6847", "website": "cogan.ca",               "status": "active",    "notes": "Canadian manufacturer. Distributed through local dealers."},
    {"id": "s9",  "name": "Equipment Roundup Mfg",        "category": "mezzanine", "phone": "800-521-2238", "website": "equipmentroundup.com",   "status": "active",    "notes": "Mezzanine systems since 1982. In-stock ships within 48hrs."},
    {"id": "s10", "name": "Spanco",                       "category": "crane",     "phone": "800-869-2080", "website": "spanco.com",             "status": "preferred", "notes": "Leading US crane manufacturer. Jib, gantry & bridge cranes. HQ in Morgantown PA."},
    {"id": "s11", "name": "Gorbel",                       "category": "crane",     "phone": "800-821-0086", "website": "gorbel.com",             "status": "active",    "notes": "Workstation cranes & overhead solutions up to 40 tons."},
    {"id": "s12", "name": "Konecranes",                   "category": "crane",     "phone": "800-946-4648", "website": "konecranes.com",         "status": "active",    "notes": "Heavy industrial bridge cranes. Seattle service center available."},
    {"id": "s13", "name": "Nordock",                      "category": "dock",      "phone": "800-722-0310", "website": "nordockinc.com",         "status": "preferred", "notes": "Full dock equipment line. Levelers, restraints, seals & shelters."},
    {"id": "s14", "name": "McGuire / Poweramp",           "category": "dock",      "phone": "800-236-6376", "website": "wbmcguire.com",          "status": "active",    "notes": "Made in USA. 60+ years manufacturing. Hydraulic & mechanical levelers."},
    {"id": "s15", "name": "Chalfant Dock Equipment",      "category": "dock",      "phone": "800-441-1223", "website": "chalfantusa.com",        "status": "active",    "notes": "Original dock seal manufacturer since 1940."},
    {"id": "s16", "name": "Pioneer Dock Equipment",       "category": "dock",      "phone": "888-327-7905", "website": "pioneerleveler.com",     "status": "active",    "notes": "40+ years manufacturing. National dealer network."},
    {"id": "s17", "name": "Panel Built",                  "category": "modular",   "phone": "800-636-3873", "website": "panelbuilt.com",         "status": "active",    "notes": "In-plant offices & modular buildings. Same vendor as mezzanines."},
    {"id": "s18", "name": "Porta-King",                   "category": "modular",   "phone": "800-284-7998", "website": "portaking.com",          "status": "active",    "notes": "Prefab modular offices. Fast lead times."},
    {"id": "s19", "name": "PortaFab",                     "category": "modular",   "phone": "800-325-3781", "website": "portafab.com",           "status": "active",    "notes": "Modular buildings & cleanrooms. Custom designs."},
    {"id": "s20", "name": "Rotary Products",              "category": "safety",    "phone": "800-457-5251", "website": "rotaryproductsinc.com",  "status": "active",    "notes": "Dock seals, rack guards, safety barriers. Made in USA since 1958."},
    {"id": "s21", "name": "Uline",                        "category": "safety",    "phone": "800-958-5463", "website": "uline.com",              "status": "preferred", "notes": "Warehouse supplies & safety products. Kent WA distribution center."},
    {"id": "s22", "name": "Grainger",                     "category": "safety",    "phone": "800-472-4643", "website": "grainger.com",           "status": "active",    "notes": "Industrial supplies. Renton & Tukwila WA locations."},
    {"id": "s23", "name": "United Rentals \u2014 Tacoma",      "category": "rental",    "phone": "253-476-0444", "website": "unitedrentals.com",      "status": "rental",    "notes": "2302 E Q St, Tacoma WA. Forklifts, scissor lifts, boom lifts, telehandlers."},
    {"id": "s24", "name": "United Rentals \u2014 Tukwila",     "category": "rental",    "phone": "206-575-0400", "website": "unitedrentals.com",      "status": "rental",    "notes": "Tukwila WA. 24/7 service. Largest rental fleet in region."},
    {"id": "s25", "name": "Equipment Depot \u2014 Kent",       "category": "rental",    "phone": "253-854-2500", "website": "eqdepot.com",            "status": "preferred", "notes": "Kent WA. Forklifts, aerials, warehouse automation. Cat, Mitsubishi brands."},
    {"id": "s26", "name": "Pacific Rim Equipment Rental", "category": "rental",    "phone": "206-441-7909", "website": "pacificrimequipmentrental.com", "status": "rental", "notes": "6515 W Marginal Way SW, Seattle WA. Forklifts 5K-10K lb, scissor lifts to 32ft."},
    {"id": "s27", "name": "Tacoma Equipment Rental",      "category": "rental",    "phone": "253-327-0555", "website": "tacomaequipmentrental.com", "status": "rental",  "notes": "Tacoma WA. Scissor lifts, boom lifts to 180ft, forklifts. Short & long term."},
    {"id": "s28", "name": "BigRentz \u2014 Tacoma",            "category": "rental",    "phone": "800-422-4369", "website": "bigrentz.com",           "status": "rental",    "notes": "Online rental marketplace. Wide equipment selection. Delivery to job site."},
]


def seed_if_empty():
    """Seed the suppliers table with the 28 default suppliers if empty."""
    with _get_conn() as conn:
        count = conn.execute("SELECT COUNT(*) FROM suppliers").fetchone()[0]
        if count > 0:
            return
    for s in _SEED_SUPPLIERS:
        create_supplier(s)
