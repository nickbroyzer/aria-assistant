"""
Ash — AI virtual assistant for Pacific Construction.

Slim entry point: creates the Flask app, registers blueprints, and starts
background threads. All routes live in routes/, all helpers in utils/.
"""

import os

from dotenv import load_dotenv
load_dotenv()

from flask import Flask

app = Flask(__name__, static_folder="static")
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.secret_key = os.getenv("SECRET_KEY", "")
if not app.secret_key:
    raise RuntimeError("SECRET_KEY environment variable is required. Set it in .env")

# ── Register all route blueprints ─────────────────────────────────────────────
from routes import register_blueprints
register_blueprints(app)

# ── Start background daemon threads ───────────────────────────────────────────
from utils.sequences import _start_followup_scheduler
from utils.invoice_inbox import _start_invoice_poller

if not app.config.get("TESTING") and os.getenv("TESTING") != "1":
    _start_followup_scheduler()
    _start_invoice_poller()

# ── Run ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
