"""
Database abstraction layer — PostgreSQL (via DATABASE_URL) or SQLite fallback.

Usage:
    from utils.database import get_connection, init_all_tables, is_postgres

    init_all_tables()  # call once at app startup

    with get_connection() as conn:
        conn.execute("SELECT * FROM suppliers WHERE id = ?", ("s1",))
        # Use ? placeholders — auto-converted to %s for PostgreSQL
"""

import os
import sqlite3
from contextlib import contextmanager

DATABASE_URL = os.environ.get("DATABASE_URL")

# Fix Railway's postgres:// → postgresql:// for psycopg2
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

SQLITE_PATH = os.path.join(os.path.dirname(__file__), "data", "suppliers.db")


def is_postgres():
    """Return True if using PostgreSQL, False if SQLite."""
    return bool(DATABASE_URL)


def _sqlite_conn():
    os.makedirs(os.path.dirname(SQLITE_PATH), exist_ok=True)
    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _pg_conn():
    import psycopg2
    import psycopg2.extras
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    return conn


class _QueryWrapper:
    """
    Wraps a database connection to normalize differences between
    SQLite and PostgreSQL:
    - Converts ? placeholders to %s for PostgreSQL
    - Returns dict-like rows for both engines
    """

    def __init__(self, conn, use_pg):
        self._conn = conn
        self._use_pg = use_pg
        self._cursor = None

    def _convert_query(self, sql):
        if self._use_pg:
            import re
            # Convert INSERT OR IGNORE → INSERT (caller uses ON CONFLICT for both)
            sql = re.sub(r'INSERT\s+OR\s+IGNORE', 'INSERT', sql, flags=re.IGNORECASE)
            # Convert :name params to %(name)s for psycopg2
            sql = re.sub(r':(\w+)', r'%(\1)s', sql)
            # Convert ? positional params to %s
            sql = sql.replace("?", "%s")
        return sql

    def execute(self, sql, params=None):
        sql = self._convert_query(sql)
        if self._use_pg:
            import psycopg2.extras
            self._cursor = self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            self._cursor.execute(sql, params or ())
            return self._cursor
        else:
            if params:
                return self._conn.execute(sql, params)
            return self._conn.execute(sql)

    def executescript(self, sql):
        if self._use_pg:
            self._cursor = self._conn.cursor()
            self._cursor.execute(sql)
        else:
            self._conn.executescript(sql)

    def fetchone(self):
        if self._cursor:
            row = self._cursor.fetchone()
            return dict(row) if row else None
        return None

    def fetchall(self):
        if self._cursor:
            rows = self._cursor.fetchall()
            if self._use_pg:
                return [dict(r) for r in rows]
            return rows
        return []

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        if self._cursor:
            self._cursor.close()
        self._conn.close()


@contextmanager
def get_connection():
    """
    Context manager that yields a _QueryWrapper.
    Auto-commits on success, rolls back on error.

    Usage:
        with get_connection() as conn:
            conn.execute("INSERT INTO sms_messages (...) VALUES (?, ?, ?)", (a, b, c))
    """
    use_pg = is_postgres()
    raw_conn = _pg_conn() if use_pg else _sqlite_conn()
    wrapper = _QueryWrapper(raw_conn, use_pg)
    try:
        yield wrapper
        wrapper.commit()
    except Exception:
        wrapper.rollback()
        raise
    finally:
        wrapper.close()


# ── Schema ────────────────────────────────────────────────────────────────────

_SQLITE_SCHEMA = """
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

CREATE TABLE IF NOT EXISTS supplier_notes (
    id          TEXT PRIMARY KEY,
    supplier_id TEXT NOT NULL REFERENCES suppliers(id) ON DELETE CASCADE,
    body        TEXT NOT NULL DEFAULT '',
    author      TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL
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

CREATE TABLE IF NOT EXISTS order_communications (
    id          TEXT PRIMARY KEY,
    order_id    TEXT NOT NULL,
    author      TEXT NOT NULL DEFAULT '',
    note        TEXT NOT NULL DEFAULT '',
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

CREATE TABLE IF NOT EXISTS retell_calls (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    call_id               TEXT UNIQUE NOT NULL,
    from_number           TEXT,
    direction             TEXT,
    start_timestamp       INTEGER,
    end_timestamp         INTEGER,
    transcript            TEXT,
    disconnection_reason  TEXT,
    received_at           TEXT
);

CREATE TABLE IF NOT EXISTS sms_messages (
    id              TEXT PRIMARY KEY,
    from_number     TEXT NOT NULL,
    to_number       TEXT NOT NULL,
    body            TEXT NOT NULL,
    direction       TEXT DEFAULT 'inbound',
    status          TEXT DEFAULT 'received',
    created_at      TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

_PG_SCHEMA = """
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
    qb_last_synced  TIMESTAMP,
    created_at      TIMESTAMP NOT NULL,
    updated_at      TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS supplier_transactions (
    id                TEXT PRIMARY KEY,
    supplier_id       TEXT NOT NULL REFERENCES suppliers(id) ON DELETE CASCADE,
    job_id            TEXT,
    type              TEXT NOT NULL DEFAULT '',
    status            TEXT NOT NULL DEFAULT 'pending',
    amount            DOUBLE PRECISION NOT NULL DEFAULT 0,
    currency          TEXT NOT NULL DEFAULT 'USD',
    description       TEXT NOT NULL DEFAULT '',
    ref_number        TEXT NOT NULL DEFAULT '',
    transaction_date  TIMESTAMP,
    due_date          TIMESTAMP,
    paid_date         TIMESTAMP,
    source            TEXT NOT NULL DEFAULT 'manual',
    qb_transaction_id TEXT,
    qb_bill_id        TEXT,
    qb_payment_id     TEXT,
    created_at        TIMESTAMP NOT NULL,
    updated_at        TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS supplier_notes (
    id          TEXT PRIMARY KEY,
    supplier_id TEXT NOT NULL REFERENCES suppliers(id) ON DELETE CASCADE,
    body        TEXT NOT NULL DEFAULT '',
    author      TEXT NOT NULL DEFAULT '',
    created_at  TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS supplier_orders (
    id                 TEXT PRIMARY KEY,
    supplier_id        TEXT NOT NULL REFERENCES suppliers(id) ON DELETE CASCADE,
    job_id             TEXT,
    description        TEXT NOT NULL DEFAULT '',
    quantity           DOUBLE PRECISION NOT NULL DEFAULT 0,
    unit               TEXT NOT NULL DEFAULT '',
    unit_price         DOUBLE PRECISION NOT NULL DEFAULT 0,
    total_amount       DOUBLE PRECISION NOT NULL DEFAULT 0,
    order_date         TIMESTAMP,
    expected_delivery  TIMESTAMP,
    delivered_date     TIMESTAMP,
    status             TEXT NOT NULL DEFAULT 'pending',
    notes              TEXT NOT NULL DEFAULT '',
    created_at         TIMESTAMP NOT NULL,
    updated_at         TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS order_communications (
    id          TEXT PRIMARY KEY,
    order_id    TEXT NOT NULL,
    author      TEXT NOT NULL DEFAULT '',
    note        TEXT NOT NULL DEFAULT '',
    created_at  TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS order_documents (
    id          TEXT PRIMARY KEY,
    order_id    TEXT NOT NULL,
    doc_type    TEXT NOT NULL,
    filename    TEXT NOT NULL,
    file_size   TEXT,
    uploaded_at TIMESTAMP NOT NULL,
    file_data   BYTEA
);

CREATE TABLE IF NOT EXISTS order_timeline (
    id          TEXT PRIMARY KEY,
    order_id    TEXT NOT NULL,
    event_type  TEXT NOT NULL,
    label       TEXT NOT NULL,
    detail      TEXT,
    actor       TEXT,
    created_at  TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS order_line_items (
    id          TEXT PRIMARY KEY,
    order_id    TEXT NOT NULL,
    description TEXT NOT NULL,
    quantity    DOUBLE PRECISION NOT NULL DEFAULT 1,
    unit_price  DOUBLE PRECISION NOT NULL DEFAULT 0,
    created_at  TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS retell_calls (
    id                    SERIAL PRIMARY KEY,
    call_id               TEXT UNIQUE NOT NULL,
    from_number           TEXT,
    direction             TEXT,
    start_timestamp       BIGINT,
    end_timestamp         BIGINT,
    transcript            TEXT,
    disconnection_reason  TEXT,
    received_at           TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sms_messages (
    id              TEXT PRIMARY KEY,
    from_number     TEXT NOT NULL,
    to_number       TEXT NOT NULL,
    body            TEXT NOT NULL,
    direction       TEXT DEFAULT 'inbound',
    status          TEXT DEFAULT 'received',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def init_all_tables():
    """Create all 10 tables using the correct schema for the active database."""
    with get_connection() as conn:
        if is_postgres():
            conn.executescript(_PG_SCHEMA)
        else:
            conn.executescript(_SQLITE_SCHEMA)
