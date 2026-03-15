"""
Ash — AI virtual assistant for Pacific Construction.

Slim entry point: creates the Flask app, registers blueprints, and starts
background threads. All routes live in routes/, all helpers in utils/.
"""

import os

from dotenv import load_dotenv
load_dotenv()

from flask import Flask, jsonify

app = Flask(__name__, static_folder="static")
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.secret_key = os.getenv("SECRET_KEY", "")
if not app.secret_key:
    raise RuntimeError("SECRET_KEY environment variable is required. Set it in .env")

# ── Register all route blueprints ─────────────────────────────────────────────
from routes import register_blueprints
register_blueprints(app)

# ── Init suppliers DB & seed defaults ─────────────────────────────────────────
from utils.suppliers_db import init_db, seed_if_empty
init_db()
seed_if_empty()

# ── Start background daemon threads ───────────────────────────────────────────
from utils.sequences import _start_followup_scheduler
from utils.invoice_inbox import _start_invoice_poller

if not app.config.get("TESTING") and os.getenv("TESTING") != "1":
    _start_followup_scheduler()
    _start_invoice_poller()

# ── Run ───────────────────────────────────────────────────────────────────────
@app.route('/api/ash/scan')
def ash_scan():
    try:
        from utils.ash_scanner import scan_inbox
        results = scan_inbox(days_back=7)
        return jsonify({'count': len(results), 'results': results})
    except Exception as e:
        return jsonify({'count': 0, 'results': [], 'error': str(e)})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
